from typing import Dict, List, Optional, TYPE_CHECKING, Sequence
import numpy as np
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
import numba
from torch import cosine_similarity
from sklearn.metrics.pairwise import cosine_similarity
numba.config.THREADING_LAYER = "omp"


if TYPE_CHECKING:
    from models import SegmentationParameters

from models import SegmentResponse, Transcript, TranscriptSegment


class SegmentationService:
    """Service for segmenting transcripts into meaningful subtopics"""
    
    async def run_bertopic(self, topic_model: BERTopic, sentences: List[str], embeddings: any) -> any:
        topics, _ = topic_model.fit_transform(sentences, embeddings)
        return topics
    
    """
    dynaseg.py
    ==========

    Dynamic-programming text segmentation for BERTopic-style sentence labels.
    -------------------------------------------------------------------------

    Given a list of *topic IDs* (one per sentence), compute a **boundary
    vector** that marks the first sentence of every "clean" topic segment.

    Key idea
    --------
    We minimise a global objective:

        total_cost =  Σ  ( disagreement_cost(segment) + λ )

    where λ ("lambda") is the price of *starting* a new segment.
    The disagreement cost of a segment [i, j) is

        (#sentences in the span) − (count of most frequent topic in the span)
consensus_boundaries
    → zero if the whole span is the same topic,
      positive if topics are mixed.

    The optimal segmentation can be found in O(n²) time with a classic
    dynamic programme (Utiyama & Isahara, 2001).  Here, n = #sentences,
    so runtime is negligible for typical documents.

    Public API
    ----------
    dp_segment(labels, lam=1.0, noise_id=-1) -> List[int]

    * labels   : List[int]  raw topic indices from BERTopic
    * lam      : float      cut penalty (higher = longer segments)
    * noise_id : int        label used for "noise"/outlier sentences
    * returns  : List[int]  boundary vector, 1 means "segment starts here"
    """
    
    # ---------------------------------------------------------------------
    # --------------  0.  tiny clean-up to remove -1 noise labels  ---------
    # ---------------------------------------------------------------------
    async def fix_noise(self, labels: List[int], embeddings: np.ndarray) -> List[int]:
        """Replace noise labels with contextually similar topic"""
        unique_topics = set(labels)
        if -1 not in unique_topics:
            return labels
            
        # Create topic similarity matrix using embeddings
        topic_centroids = np.array([np.mean(embeddings[np.array(labels) == t], axis=0) 
                                for t in unique_topics if t != -1])
        
        # Replace noise points with most similar topic
        for i, label in enumerate(labels):
            if label == -1:
                similarities = cosine_similarity([embeddings[i]], topic_centroids)
                labels[i] = list(unique_topics)[np.argmax(similarities)]
                
        return labels
    # ---------------------------------------------------------------------
    # --------------  1.  build prefix topic counts (O(n·|T|)) -------------
    # ---------------------------------------------------------------------
    async def prefix_counts(self, labels: Sequence[int]) -> Dict[int, List[int]]:
        """
        freq[t][j] =   how many times topic *t* occurs in sentences 0…j-1
        Shape:  { topic_id → (n+1)-long list }.
        """
        n = len(labels)
        topics = set(labels)
        freq: Dict[int, List[int]] = {t: [0] * (n + 1) for t in topics}

        for j, z in enumerate(labels, start=1):        # 1-based prefix index
            for t in topics:
                freq[t][j] = freq[t][j - 1] + (1 if z == t else 0)

        return freq


    # ---------------------------------------------------------------------
    # --------------  2.  dynamic-programming segmentation  ----------------
    # ---------------------------------------------------------------------
    from sklearn.metrics.pairwise import cosine_similarity

    async def dp_segment(self, labels: List[int], embeddings, noise_id: int, lam: float, similarity_threshold=0.75) -> List[int]:
        """
        Perform DP segmentation and return a *boundary vector* of the
        same length as `labels`.  Entry i == 1  ⇒  sentence i starts a segment.
        """
        # -- Step 0  (optional) noise clean-up ---------------------------------
        clean = await self.fix_noise(labels, noise_id)

        n = len(clean)
        if n == 0:
            return []

        # -- Step 1  prefix frequency table ------------------------------------
        freq = await self.prefix_counts(clean)
        topics = list(freq.keys())                    # stable order

        # helper: O(|topics|) cost of treating [i, j) as one block
        def span_cost(i: int, j: int) -> int:
            span_len = j - i
            max_same_topic = max(freq[t][j] - freq[t][i] for t in topics)
            return span_len - max_same_topic          # disagreement count

        def adjust_lambda(lam: float, i: int, j: int) -> float:
            """
            Adjust lambda based on the length of the segment.
            """
            span_len = j - i
            if span_len >= 240:
                return lam * 2.0
            elif span_len <= 120:
                return lam * 2.0
            return lam

        # -- Step 2  dynamic programme -----------------------------------------
        dp = [float("inf")] * (n + 1)                 # best cost for prefix 0…j
        back = [0] * (n + 1)                          # best predecessor index
        dp[0] = -2*lam                                  # so first segment pays +λ once
    
        for j in range(1, n + 1):                     # end position (exclusive)
            for i in range(j):                        # candidate previous cut
                cost = dp[i] + span_cost(i, j) + adjust_lambda(lam, i, j)  # block cost + λ
                if cost < dp[j]:
                    dp[j] = cost
                    back[j] = i

        # -- Step 3  back-trace to create boundary vector ----------------------
        boundaries = [0] * n
        k = n
        while k > 0:
            i = back[k]
            boundaries[i] = 1                         # sentence i starts segment
            k = i                                     # jump to previous cut
        
        # Post-processing merging based on similarity
        for i in range(1, len(embeddings) - 1):
            # Check if both current and next sentence are not segment boundaries
            if boundaries[i] == 0 and boundaries[i + 1] == 0:
                sim = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
                if sim > similarity_threshold:
                    # Merge by removing the boundary at i+1
                    boundaries[i + 1] = 0

        return boundaries

    async def consensus_boundaries(self, boundary_runs, min_sep, method):
        """
        Fuse N binary boundary vectors into one consensus vector.

        Parameters
        ----------
        boundary_runs : List[np.ndarray]  each shape (n,), entries 0/1
        min_sep       : int  hard minimum gap between consecutive cuts
        method        : "topk" | "threshold" | "localmax"
            topk       – take K = median #cuts and pick top-K probs
            threshold  – pick all positions with p ≥ 0.5
            localmax   – pick local maxima separated by ≥ min_sep

        Returns
        -------
        consensus : np.ndarray shape (n,), entries 0/1
        p         : np.ndarray shape (n,) probability profile
        """
        B = np.stack(boundary_runs)           # (N, n)
        p = B.mean(axis=0)                    # boundary probability at each index
        n = p.size
        consensus = np.zeros(n, dtype=int)

        if method == "topk":
            K = int(np.median(B.sum(axis=1)))        # median #cuts
            # indices sorted by probability, highest first
            idx = np.argsort(-p)
            chosen = []
            for j in idx:
                if all(abs(j - c) >= min_sep for c in chosen):
                    chosen.append(j)
                if len(chosen) == K:
                    break
            consensus[chosen] = 1

        elif method == "threshold":
            consensus[p >= 0.5] = 1

        elif method == "localmax":
            for j in range(1, n - 1):
                if p[j] > p[j - 1] and p[j] >= p[j + 1] and p[j] >= 0.2:
                    # enforce min_sep
                    if consensus[max(0, j - min_sep):j].sum() == 0:
                        consensus[j] = 1
        else:
            raise ValueError("unknown method")

        consensus[0] = 1                      # first sentence always a boundary
        return consensus, p
    
    # Add intermediate segments to reduce large gaps
    async def add_intermediate_segments(self, segment_indices, chunks: List[TranscriptSegment], max_gap_seconds):
        """Add intermediate segments if gaps are too large (>5 minutes)"""
        new_indices = list(segment_indices)
        
        for i in range(len(segment_indices) - 1):
            start_idx = segment_indices[i]
            end_idx = segment_indices[i + 1]
            
            # Get time range for this gap
            start_time = chunks[start_idx].timestamp[1] if start_idx < len(chunks) else 0
            end_time = chunks[end_idx].timestamp[0] if end_idx < len(chunks) else start_time
            gap_duration = end_time - start_time
            
            # If gap is too large, add intermediate segments
            if gap_duration > max_gap_seconds:
                num_splits = int(gap_duration / max_gap_seconds)
                chunk_gap = end_idx - start_idx
                
                for split_num in range(1, num_splits + 1):
                    # Calculate intermediate index proportionally
                    intermediate_idx = start_idx + int((chunk_gap * split_num) / (num_splits + 1))
                    
                    # Make sure it's not too close to existing boundaries
                    if (intermediate_idx not in new_indices and 
                        intermediate_idx > start_idx + 3 and 
                        intermediate_idx < end_idx - 3):
                        new_indices.append(intermediate_idx)
        
        return np.sort(np.array(new_indices))

    async def segment_transcript(self, transcript: Transcript, segmentation_params: Optional['SegmentationParameters'] = None) -> SegmentResponse:
        """
        Segment transcript into meaningful subtopics using LLM
        Returns: Dictionary with end_time as key and cleaned transcript as value
        """
        print("Segmentation params given:", segmentation_params.lam, segmentation_params.runs, segmentation_params.noiseId)
        # Extract model from parameters or use default
        lam = 2.0
        runs = 25
        noise_id = -1

        if segmentation_params and segmentation_params.lam:
            lam = segmentation_params.lam
        if segmentation_params and segmentation_params.runs:
            runs = segmentation_params.runs
        if segmentation_params and segmentation_params.noiseId:
            noise_id = segmentation_params.noiseId

        print(f"Segmentation parameters: lambda={lam}, runs={runs}, noise_id={noise_id}")
        
        if not transcript:
            raise ValueError("Transcript text is required and must be a non-empty string.")

        chunks = transcript.chunks

        transcript_sentences = []
        for chunk in chunks:
            transcript_sentences.append(chunk.text)

        #Generate Embedding of transcript sentences and find topics
        sentences = transcript_sentences
        embedder = SentenceTransformer("all-mpnet-base-v2")
        embeddings = embedder.encode(sentences)
        topic_model = BERTopic(min_topic_size=2)

        # Run BERTopic multiple times for consensus
        boundary_runs = []

        for _ in range(runs):
            topics = await self.run_bertopic(topic_model, sentences, embeddings)
            boundaries = await self.dp_segment(topics, embeddings, noise_id, lam=lam, similarity_threshold=0.75)
            boundary_runs.append(np.array(boundaries))
        
        # Get consensus boundaries
        consensus, _ = await self.consensus_boundaries(boundary_runs, min_sep=3, method="topk")
        
        # Get relevant chunk indices where segments start
        segment_start_indices = np.where(consensus)[0]
        # Apply intermediate segment addition
        segment_start_indices = await self.add_intermediate_segments(segment_start_indices, chunks, max_gap_seconds=350)
        
        # Create segments dictionary
        segments = {}
        
        for i, start_idx in enumerate(segment_start_indices):
            # Determine end index for this segment
            if i < len(segment_start_indices) - 1:
                end_idx = segment_start_indices[i + 1]
            else:
                end_idx = len(chunks)
            
            # Collect all text in this segment
            segment_text = ""
            segment_chunks = chunks[start_idx:end_idx]
            
            for chunk in segment_chunks:
                segment_text += chunk.text + " "
            
            # Use the endtime of the last chunk in the segment as the key
            last_chunk = chunks[end_idx - 1]
            # Handle the timestamp format: [start_time, end_time]
            if last_chunk.timestamp and isinstance(last_chunk.timestamp, list) and len(last_chunk.timestamp) == 2:
                endtime = last_chunk.timestamp[1]  # Get end_time from timestamp array
            else:
                raise ValueError(f"Invalid timestamp format for chunk {last_chunk}. Expected [start_time, end_time] array.")
            
            # Clean up the segment text
            segment_text = segment_text.strip()
            
            segments[str(endtime)] = segment_text
            print("Segment created:", segments)
        
        return SegmentResponse(segments=segments, segment_count=len(segment_start_indices))
