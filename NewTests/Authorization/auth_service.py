from fastapi import FastAPI
import logging
from models import *
import pprint

# Sample Authorization service that is started when the test starts.
# It does not check token validity and simply implements a set of basic users


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

app = FastAPI()



@app.post("/user/get-profile") 
def get_user_profile(user_profile_request: UserProfileRequest):
    logging.info("get user profile: " + user_profile_request.json())

    p = UserProfileResponse(
        name="anonymous",
        permissions=[],
        authorized_labels=[],
        validity=60
    )

    if user_profile_request.token_key == "user-token-key":
        if user_profile_request.token_value == "token-uploader":
            p = UserProfileResponse(
                name="uploader",
                permissions=["upload", "edit-labels", "delete", "view"],
                authorized_labels=["*"],
                validity=60
            )
        elif user_profile_request.token_value == "token-admin":
            p = UserProfileResponse(
                name="admin",
                permissions=["all"],
                authorized_labels=["*"],
                validity=60
            )
        elif user_profile_request.token_value == "token-user-a":
            p = UserProfileResponse(
                name="user-a",
                permissions=["view"],
                authorized_labels=["label_a"],
                validity=60
            )

    return p        


@app.post("/tokens/validate")
def validate_authorization(request: TokenValidationRequest):

    logging.info("validating token: " + request.json())

    granted = False
    if request.token_value == "token-knix-study":
        granted = request.orthanc_id == "b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0"

    response = TokenValidationResponse(
        granted=granted,
        validity=60
    )

    logging.info("validate token: " + response.json())
    return response
