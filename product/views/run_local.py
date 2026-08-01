
from django.http import FileResponse
import networkx as nx
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView



import dotenv

from product.run_local import run_local
from product.stem_graph_table import build_stem_graph_table

dotenv.load_dotenv()

"""
# Per-step timings written after each run
TIMING_PATH = os.path.abspath(
os.path.join(tmp_store.name, 'logs', 'execution_timing.json'))
os.makedirs(TIMING_PATH, exist_ok=True)

# Execution metadata uploaded to GCS session output dir
METADATA_PATH = os.path.abspath(os.path.join(tmp_store.name, 'logs', 'metadata.json'))
os.makedirs(METADATA_PATH, exist_ok=True)

# Out dir
OUTPUT_PATH = os.path.abspath(os.path.join(tmp_store.name, 'output'))
os.makedirs(OUTPUT_PATH, exist_ok=True)
"""


class RunLocalSampleView(APIView):

    def post(self, request):
        files = request.FILES.getlist("files")
        annotate_variants = str(
            request.data.get("annotate_variants", "false")
        ).lower() in {"1", "true", "yes", "on"}
        functions = [
            value.strip()
            for value in str(
                request.data.get("functional_annotation", "")
            ).replace("\n", ",").split(",")
            if value.strip()
        ]
        cfg = {
            "protein": {
                "functional_annotation": functions,
                "function_similarity_threshold": float(
                    request.data.get("function_similarity_threshold", 0.75)
                ),
            }
        }
        graph = None
        try:
            graph = run_local(
                files,
                annotate_variants=annotate_variants,
                cfg=cfg,
            )
            serializable_graph = graph.check_serilize(graph.G)
            graph_payload = nx.node_link_data(serializable_graph)
            stem_graph_table = build_stem_graph_table(serializable_graph)
            return Response(
                {
                    "status": "complete",
                    "summary": {
                        "nodes": serializable_graph.number_of_nodes(),
                        "edges": serializable_graph.number_of_edges(),
                        "samples": len(graph.workflow_result.get("result_ids", [])),
                    },
                    "workflow_result": graph.workflow_result,
                    "graph": graph_payload,
                    "stem_graph_table": stem_graph_table,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            print("Err1", exc)
            return Response(
                {"detail": "StemCNV graph processing failed", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        finally:
            if graph is not None:
                graph.close()
