"""
ImageProcessorLambda
---------------------
Triggered by: SQS (image-processing-queue), which is fed by an S3 Event
              Notification on the Upload Bucket.
Reads:   Upload Bucket (raw images)
Writes:  Processed Bucket -> multiple resized/watermarked variants (JPEG)
         DynamoDB          -> metadata (EXIF, sizes, moderation result, status)

Environment variables:
    DYNAMODB_TABLE_NAME      -> e.g. ImageMetadata                 (required)
    PROCESSED_IMAGES_BUCKET  -> e.g. proj-processed-xxxx-us-east-1  (required)
    WATERMARK_TEXT           -> default "Processed by Kareem"       (optional)
    IMAGE_SIZES              -> e.g. "thumbnail:150,medium:600,large:1600"
                                 (optional, default below)
    ENABLE_MODERATION        -> "true"/"false", default "false"     (optional)
    MODERATION_MIN_CONFIDENCE-> default "80"                        (optional)

Design notes / lessons applied (see docs/lessons-learned.md):
    - urllib.parse.unquote_plus() on the S3 object key (handles spaces/symbols)
    - explicit ContentType on every upload_file (avoids binary/octet-stream)
    - per-message try/except + batchItemFailures (partial batch failure support,
      so one corrupt image in a batch of 5 does NOT force-retry the other 4)
    - Customer Managed KMS key used at the bucket level (not aws/s3)
    - EXIF is read defensively: many real-world images have partial/corrupt
      EXIF blocks, so a failure here must never fail the whole job.
    - Rekognition is optional and fails "open but flagged": if the moderation
      call itself errors (throttling, region mismatch, etc.) we still store
      the image and mark ModerationStatus = "MODERATION_UNAVAILABLE" instead
      of blocking the pipeline on an availability problem in a *different*
      AWS service.
"""

import json
import os
import io
import boto3
import mimetypes
import urllib.parse
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont, ExifTags

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
rekognition_client = boto3.client('rekognition')

TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'ImageMetadata')
PROCESSED_BUCKET = os.environ['PROCESSED_IMAGES_BUCKET']
WATERMARK_TEXT = os.environ.get('WATERMARK_TEXT', 'Processed by Kareem')
ENABLE_MODERATION = os.environ.get('ENABLE_MODERATION', 'false').lower() == 'true'
MODERATION_MIN_CONFIDENCE = float(os.environ.get('MODERATION_MIN_CONFIDENCE', '80'))

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# Multiple output formats, matching the "resize into multiple formats"
# architecture requirement. Format: "name:max_dimension_px"
DEFAULT_SIZES = "thumbnail:150,medium:600,large:1600"


def parse_sizes():
    raw = os.environ.get('IMAGE_SIZES', DEFAULT_SIZES)
    sizes = {}
    for part in raw.split(','):
        name, _, dim = part.partition(':')
        name = name.strip()
        try:
            sizes[name] = int(dim.strip())
        except ValueError:
            continue
    return sizes or {"thumbnail": 150, "medium": 600, "large": 1600}


IMAGE_SIZES = parse_sizes()


def get_content_type(source_bucket, object_key):
    """Fetch Content-Type from the source object, fall back to extension guess."""
    try:
        head = s3_client.head_object(Bucket=source_bucket, Key=object_key)
        content_type = head.get('ContentType')
    except Exception:
        content_type = None

    if not content_type or content_type == 'binary/octet-stream':
        guessed_type, _ = mimetypes.guess_type(object_key)
        content_type = guessed_type or 'image/jpeg'
    return content_type


def extract_exif(img):
    """
    Best-effort EXIF extraction. Returns a small, DynamoDB-safe dict
    (only JSON-serialisable scalar values — EXIF sometimes contains raw
    bytes/tuples that DynamoDB's boto3 resource layer cannot store).
    """
    exif_data = {}
    try:
        raw_exif = img.getexif()
        if not raw_exif:
            return exif_data
        for tag_id, value in raw_exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if isinstance(value, (str, int, float)):
                exif_data[tag_name] = value
            elif isinstance(value, bytes):
                continue  # skip raw binary EXIF blocks (e.g. thumbnails)
            else:
                exif_data[tag_name] = str(value)
    except Exception as e:
        print(f"EXIF extraction skipped (non-fatal): {e}")
    return exif_data


def moderate_image(bucket, key):
    """
    Optional content moderation via Amazon Rekognition. Non-fatal:
    any error here degrades to MODERATION_UNAVAILABLE, it never raises.
    """
    if not ENABLE_MODERATION:
        return {"ModerationStatus": "SKIPPED", "ModerationLabels": []}

    try:
        response = rekognition_client.detect_moderation_labels(
            Image={"S3Object": {"Bucket": bucket, "Name": key}},
            MinConfidence=MODERATION_MIN_CONFIDENCE
        )
        labels = [
            {"Name": lbl["Name"], "Confidence": round(lbl["Confidence"], 2)}
            for lbl in response.get("ModerationLabels", [])
        ]
        status = "FLAGGED" if labels else "CLEAN"
        return {"ModerationStatus": status, "ModerationLabels": labels}
    except Exception as e:
        print(f"Rekognition moderation failed (non-fatal): {e}")
        return {"ModerationStatus": "MODERATION_UNAVAILABLE", "ModerationLabels": []}


def add_watermark(img):
    """Add a semi-transparent text watermark to the bottom-right corner."""
    width, height = img.size
    font_size = max(14, width // 25)
    try:
        font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    draw_tmp = ImageDraw.Draw(img)
    bbox = draw_tmp.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]

    padding = 8
    x = max(0, width - text_width - padding * 2)
    y = max(0, height - text_height - padding * 2)

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
        fill=(0, 0, 0, 140)
    )
    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    ImageDraw.Draw(img).text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 230))
    return img


def process_image_variants(input_path, safe_base_name):
    """
    Opens the source image once, extracts EXIF, then produces one
    watermarked JPEG per configured size (thumbnail/medium/large).
    Returns (exif_dict, {variant_name: (local_path, s3_key, byte_size)}).
    """
    variants = {}
    with Image.open(input_path) as original:
        exif_data = extract_exif(original)
        original_mode = original.mode
        base_rgba = original.convert('RGBA') if original_mode in ('RGBA', 'P') else original.convert('RGB')

        for variant_name, max_dim in IMAGE_SIZES.items():
            img = base_rgba.copy()
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            img = add_watermark(img)

            local_path = f"/tmp/{safe_base_name}_{variant_name}.jpg"
            img.convert('RGB').save(local_path, quality=90, optimize=True)

            s3_key = f"processed/{variant_name}/{safe_base_name}.jpg"
            variants[variant_name] = (local_path, s3_key, os.path.getsize(local_path))

    return exif_data, variants


def process_single_record(s3_record, table):
    """Process exactly one S3 ObjectCreated record. Raises on failure."""
    source_bucket = s3_record['s3']['bucket']['name']
    object_key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'])
    object_size = s3_record['s3']['object']['size']

    ext = os.path.splitext(object_key)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        print(f"Skipping unsupported file type: {object_key}")
        return

    print(f"Processing: {object_key} from {source_bucket} ({object_size} bytes)")

    download_path = f'/tmp/{os.path.basename(object_key)}'
    s3_client.download_file(source_bucket, object_key, download_path)

    content_type = get_content_type(source_bucket, object_key)

    base_name = os.path.splitext(os.path.basename(object_key))[0]
    safe_base_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in base_name)

    exif_data, variants = process_image_variants(download_path, safe_base_name)

    uploaded_variants = {}
    for variant_name, (local_path, s3_key, byte_size) in variants.items():
        s3_client.upload_file(
            local_path,
            PROCESSED_BUCKET,
            s3_key,
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
        uploaded_variants[variant_name] = {"Key": s3_key, "SizeBytes": byte_size}
        print(f"Uploaded [{variant_name}] -> {PROCESSED_BUCKET}/{s3_key}")

    # Moderation runs against the "large" (or first available) uploaded variant
    moderation_target_key = uploaded_variants.get(
        "large", next(iter(uploaded_variants.values()))
    )["Key"]
    moderation_result = moderate_image(PROCESSED_BUCKET, moderation_target_key)

    image_id = object_key.replace('/', '_').replace('.', '-')
    table.put_item(Item={
        'ImageId': image_id,
        'OriginalKey': object_key,
        'SourceBucket': source_bucket,
        'ProcessedBucket': PROCESSED_BUCKET,
        'ProcessedVariants': uploaded_variants,
        'UploadTime': datetime.now(timezone.utc).isoformat(),
        'Status': 'Processed',
        'OriginalSize': object_size,
        'OriginalContentType': content_type,
        'Exif': exif_data,
        **moderation_result
    })
    print(f"Metadata stored for ImageId: {image_id} "
          f"(moderation={moderation_result['ModerationStatus']})")

    for variant_name, (local_path, _, _) in variants.items():
        if os.path.exists(local_path):
            os.remove(local_path)
    if os.path.exists(download_path):
        os.remove(download_path)


def lambda_handler(event, context):
    """
    SQS trigger handler. Returns batchItemFailures so SQS only retries the
    messages that actually failed (partial batch failure — see
    docs/implementation_guide.md section 4.2). After 3 failed receives the
    Redrive Policy moves the message to the DLQ automatically.
    """
    table = dynamodb.Table(TABLE_NAME)
    failed_ids = []

    for record in event['Records']:
        message_id = record['messageId']
        try:
            s3_event = json.loads(record['body'])

            if s3_event.get('Event') == 's3:TestEvent':
                print("Received S3 test event notification, skipping.")
                continue

            for s3_record in s3_event.get('Records', []):
                process_single_record(s3_record, table)

        except Exception as e:
            print(f"Failed processing message {message_id}: {e}")
            failed_ids.append(message_id)

    return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failed_ids]}
