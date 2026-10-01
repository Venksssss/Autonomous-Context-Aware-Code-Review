from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.schemas.review_planner import ReviewPlan, ReviewPlanRequest
from app.schemas.review_workflow import ReviewWorkflowRequest, ReviewWorkflowResult
from app.services.review_planner import ReviewPlannerService
from app.services.review_workflow import ReviewWorkflowService

router = APIRouter()

@router.post("/review-plan", response_model=ReviewPlan)
def generate_review_plan(request: ReviewPlanRequest):
    try:
        service = ReviewPlannerService()
        plan = service.generate_plan(request.request, request.repository_context)
        return plan
    except ValueError as e:
        return JSONResponse(status_code=500, content={"error": {"code": "LLM_CONFIGURATION_ERROR", "message": str(e)}})
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": {"code": "LLM_INVOCATION_ERROR", "message": str(e)}})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}})


@router.post("/review", response_model=ReviewWorkflowResult)
def run_review_workflow(request: ReviewWorkflowRequest):
    """
    Full orchestrated review via LangGraph.

    Routes call ReviewWorkflowService (not LangGraph directly) so that
    the graph, state management, and diff retrieval remain encapsulated.
    """
    try:
        service = ReviewWorkflowService()
        result = service.run(
            review_request=request.review_request,
            repository_path=request.repository_path,
            base_revision=request.base_revision,
            head_revision=request.head_revision,
        )
        return result
    except ValueError as e:
        return JSONResponse(status_code=500, content={"error": {"code": "LLM_CONFIGURATION_ERROR", "message": str(e)}})
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": {"code": "LLM_INVOCATION_ERROR", "message": str(e)}})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}})
