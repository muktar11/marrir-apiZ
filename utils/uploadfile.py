import os
import shutil
from tempfile import NamedTemporaryFile
import uuid

from fastapi import UploadFile
from core.security import settings


def uploadFileToLocal(file: UploadFile):
    try:
        file_extension = os.path.splitext(file.filename)[1]
        if file_extension.lower() not in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi', '.wmv', '.pdf']:
            raise ValueError("Unsupported file type.")
        
        file_type = None
        if file_extension.lower() in ['.mp4', '.mov', '.avi', '.wmv']:
            file_type = "videos"
        elif file_extension.lower() in ['.jpg', '.jpeg', '.png']:
            file_type = "images"
        else:
            file_type = "documents"

        temp_file = NamedTemporaryFile(delete=False, suffix=file_extension)
        with temp_file as buffer:
            shutil.copyfileobj(file.file, buffer)

        os.makedirs(f"static/{file_type}/uploads/", exist_ok=True)
        final_path = os.path.join(f"static/{file_type}/uploads/", f"{uuid.uuid4()}{file_extension}")
        shutil.move(temp_file.name, final_path)

        return "/".join(final_path.split("/")[1:])
    except Exception as e:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
        raise e


def uploadFileToS3(s3_client, file: UploadFile):
    file_extension = os.path.splitext(file.filename)[1]
    s3_file_key = f"{str(uuid.uuid4())}{file_extension}"

    s3_client.upload_fileobj(file.file, settings.AWS_BUCKET_NAME, s3_file_key)

    s3_file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.amazonaws.com/{s3_file_key}"

    return s3_file_url


def uploadFileToGoogleCloud(storage_client, file: UploadFile):
    file_extension = os.path.splitext(file.filename)[1]
    gcs_file_name = f"{str(uuid.uuid4())}{file_extension}"

    bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_file_name)

    blob.upload_from_file(file.file, content_type=file.content_type)

    gcs_file_url = (
        f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{gcs_file_name}"
    )

    return gcs_file_url
