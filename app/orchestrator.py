from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from app.models.planner import GeneratePlanRequest, StorePlanRequest
from app.agents.agent import AgentOrchestrator
from app.services.s3_manager import S3Manager
from app.config import OPENAI, GITHUB_REDIRECT_URI
import logging
import json
import datetime
from dateutil import parser

router = APIRouter()

@router.post("/api/planner/generate")
async def generate_plan_endpoint(plan_request: GeneratePlanRequest):
    try:
        logging.info(f"Received plan request: {plan_request.dict()}")
        
        orchestrator = AgentOrchestrator(
            provider=plan_request.provider,
            model=plan_request.model,
            api_key=OPENAI,
            api_base_url=GITHUB_REDIRECT_URI
        )

        timestamp = parser.isoparse(plan_request.timestamp)

        result = await orchestrator.generate_plan(
            plan_request.prompt,
            plan_request.repo_name,
            plan_request.hash,
            str(timestamp),
            
            # plan_request.user_login, 
            # plan_request.access_token
        )
        logging.info(f"Generated plan: {result}")

        # Ensure we're always returning a string
        if isinstance(result, str):
            return {"result": result}
        else:
            return {"result": json.dumps(result, indent=2)}
        
    except ValidationError as e:
        logging.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logging.error(f"Error in generate_plan_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/planner/store")
async def store_plan_endpoint(plan_request: StorePlanRequest):
    try:
        logging.info(f"Received store plan request: {plan_request.dict()}")
        
        s3_manager = S3Manager(plan_request.hash, plan_request.repo_name)
        
        # upload the json file to the s3 bucket at the specified hash
        s3_manager.upload_json_object(plan_request.plan)

        return {"status": "success", "description": "json file uploaded to s3", "timestamp": datetime.datetime.now()}
    except ValidationError as e:
        logging.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logging.error(f"Error in store_plan_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))