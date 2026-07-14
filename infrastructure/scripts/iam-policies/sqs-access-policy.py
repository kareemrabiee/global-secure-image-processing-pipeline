{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowUploadBucketToSendMessage",
      "Effect": "Allow",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:us-east-1:${AWS_ACCOUNT_ID}:kareem-img-proc-queue",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${AWS_ACCOUNT_ID}"
        },
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:s3:::kareem-img-proc-upload-${AWS_ACCOUNT_ID}-us-east-1-an"
        }
      }
    },
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "sqs:*",
      "Resource": "arn:aws:sqs:us-east-1:${AWS_ACCOUNT_ID}:kareem-img-proc-queue",
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}