import sys, aml_pipeline
print("aml_pipeline location:", aml_pipeline.__file__)
print("sys.path[:5]:", sys.path[:5])
from aml_pipeline.pipelines.daily_pipeline import _run_evm_extract
import inspect
print("_run_evm_extract defined in:", inspect.getfile(_run_evm_extract))
