from app.services.google_services import get_current_user
from fastapi import HTTPException, Request, APIRouter, Depends
from fastapi.responses import JSONResponse
from firebase_admin import db, auth

import logging

router = APIRouter()

@router.post("/google-signin")
async def google_signin(request: Request):
    try:
        data = await request.json()
        id_token = data.get('idToken')
        if not id_token:
            raise HTTPException(status_code=400, detail="Missing ID token")

        # Verify the ID token
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token['uid']

        # Create or update user entry in Firebase Realtime Database
        ref = db.reference('users')
        user_data = ref.child(user_id).get()
        
        if not user_data:
            # If user doesn't exist, create a new entry
            ref.child(user_id).set({
                'email': decoded_token.get('email'),
                'displayName': decoded_token.get('name'),
                'github_token': None,
                'github_username': None
            })
        else:
            # If user exists, update the entry
            ref.child(user_id).update({
                'email': decoded_token.get('email'),
                'displayName': decoded_token.get('name'),
                'logged_in': "true"
            })

        logging.info(f"User {user_id} signed in with Google")
        return JSONResponse(content={"message": "Google sign-in successful"})

    except Exception as e:
        logging.error(f"Error in google_signin: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    user_id = current_user['uid']
    logging.info(f"Logging out user: {user_id}")
    try:
        ref = db.reference(f'users/{user_id}')
        ref.update({
            'logged_in': "false"
        })
        logging.info(f"User {user_id} logged out successfully")
        return {"message": "Logged out successfully"}
    except Exception as e:
        logging.error(f"Error during logout for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error during logout")
