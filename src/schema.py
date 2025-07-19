from typing import List
from pydantic import BaseModel


SOL_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["SELECT_ONE_IN_LOT"]
                },
                "isParameterized": {"type": "boolean"},
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "possibleValues": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "type": {"type": "string"}
                        },
                        "required": ["name", "possibleValues", "type"]
                    }
                },
                "hint": {"type": "string"},
                "timeLimitSeconds": {"type": "number"},
                "points": {"type": "number"}
            },
            "required": [
                "text",
                "type",
                "isParameterized",
                "timeLimitSeconds",
                "points"
            ]
        },
        "solution": {
            "type": "object",
            "properties": {
                "incorrectLotItems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "explaination": {"type": "string"}
                        },
                        "required": ["text", "explaination"]
                    }
                },
                "correctLotItem": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "explaination": {"type": "string"}
                    },
                    "required": ["text", "explaination"]
                }
            },
            "required": ["incorrectLotItems", "correctLotItem"]
        }
    },
    "required": ["question", "solution"]
}

SML_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["SELECT_MANY_IN_LOT"]
                },
                "isParameterized": {"type": "boolean"},
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "possibleValues": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "type": {"type": "string"}
                        },
                        "required": ["name", "possibleValues", "type"]
                    }
                },
                "hint": {"type": "string"},
                "timeLimitSeconds": {"type": "number"},
                "points": {"type": "number"}
            },
            "required": [
                "text",
                "type",
                "isParameterized",
                "timeLimitSeconds",
                "points"
            ]
        },
        "solution": {
            "type": "object",
            "properties": {
                "incorrectLotItems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "explaination": {"type": "string"}
                        },
                        "required": ["text", "explaination"]
                    }
                },
                "correctLotItems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "explaination": {"type": "string"}
                        },
                        "required": ["text", "explaination"]
                    }
                }
            },
            "required": ["incorrectLotItems", "correctLotItems"]
        }
    },
    "required": ["question", "solution"]
}

OTL_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["ORDER_THE_LOTS"]
                },
                "isParameterized": {"type": "boolean"},
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "possibleValues": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "type": {"type": "string"}
                        },
                        "required": ["name", "possibleValues", "type"]
                    }
                },
                "hint": {"type": "string"},
                "timeLimitSeconds": {"type": "number"},
                "points": {"type": "number"}
            },
            "required": [
                "text",
                "type",
                "isParameterized",
                "timeLimitSeconds",
                "points"
            ]
        },
        "solution": {
            "type": "object",
            "properties": {
                "ordering": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lotItem": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "explaination": {"type": "string"}
                                },
                                "required": ["text", "explaination"]
                            },
                            "order": {"type": "number"}
                        },
                        "required": ["lotItem", "order"]
                    }
                }
            },
            "required": ["ordering"]
        }
    },
    "required": ["question", "solution"]
}

NAT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["NUMERIC_ANSWER_TYPE"]
                },
                "isParameterized": {"type": "boolean"},
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "possibleValues": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "type": {"type": "string"}
                        },
                        "required": ["name", "possibleValues", "type"]
                    }
                },
                "hint": {"type": "string"},
                "timeLimitSeconds": {"type": "number"},
                "points": {"type": "number"}
            },
            "required": [
                "text",
                "type",
                "isParameterized",
                "timeLimitSeconds",
                "points"
            ]
        },
        "solution": {
            "type": "object",
            "properties": {
                "decimalPrecision": {"type": "number"},
                "upperLimit": {"type": "number"},
                "lowerLimit": {"type": "number"},
                "value": {"type": "number"},
                "expression": {"type": "string"}
            },
            "required": ["decimalPrecision", "upperLimit", "lowerLimit"]
        }
    },
    "required": ["question", "solution"]
}

DES_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": ["DESCRIPTIVE"]
                },
                "isParameterized": {"type": "boolean"},
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "possibleValues": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "type": {"type": "string"}
                        },
                        "required": ["name", "possibleValues", "type"]
                    }
                },
                "hint": {"type": "string"},
                "timeLimitSeconds": {"type": "number"},
                "points": {"type": "number"}
            },
            "required": [
                "text",
                "type",
                "isParameterized",
                "timeLimitSeconds",
                "points"
            ]
        },
        "solution": {
            "type": "object",
            "properties": {
                "solutionText": {"type": "string"}
            },
            "required": ["solutionText"]
        }
    },
    "required": ["question", "solution"]
}