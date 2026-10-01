from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.schemas.review_planner import ReviewPlan, ReviewPlanRequest
from app.services.review_planner import ReviewPlannerService

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
