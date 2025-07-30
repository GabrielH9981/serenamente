import cloudinary
import cloudinary.uploader
import os

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

def upload_image(file, public_id=None):
    response = cloudinary.uploader.upload(
        file,
        folder="serenamente/perfis",
        public_id=public_id,
        overwrite=True,
        transformation=[
            {"width": 300, "height": 300, "crop": "fill", "gravity": "face", "quality": "auto"}
        ]
    )
    return response["secure_url"]
