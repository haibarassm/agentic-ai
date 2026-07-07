"""L5 流水线编排：L1→L2→L4闸门→L3。"""

from .run import L4GateError, PipelineResult, run_pipeline

__all__ = ["run_pipeline", "PipelineResult", "L4GateError"]
