{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "ReadUploadBucket",
			"Effect": "Allow",
			"Action": [
				"s3:GetObject"
			],
			"Resource": "arn:aws:s3:::kareem-img-proc-upload-${AWS_ACCOUNT_ID}-us-east-1-an/*"
		},
		{
			"Sid": "WriteProcessedBucket",
			"Effect": "Allow",
			"Action": [
				"s3:PutObject"
			],
			"Resource": "arn:aws:s3:::kareem-img-proc-processed-${AWS_ACCOUNT_ID}-us-east-1-an/*"
		},
		{
			"Sid": "SQSConsume",
			"Effect": "Allow",
			"Action": [
				"sqs:ReceiveMessage",
				"sqs:DeleteMessage",
				"sqs:GetQueueAttributes"
			],
			"Resource": "arn:aws:sqs:us-east-1:${AWS_ACCOUNT_ID}:kareem-img-proc-queue"
		},
		{
			"Sid": "DynamoWrite",
			"Effect": "Allow",
			"Action": [
				"dynamodb:PutItem"
			],
			"Resource": "arn:aws:dynamodb:us-east-1:${AWS_ACCOUNT_ID}:table/ImageMetadata"
		},
		{
			"Sid": "KMSUsage",
			"Effect": "Allow",
			"Action": [
				"kms:Decrypt",
				"kms:GenerateDataKey"
			],
			"Resource": "arn:aws:kms:us-east-1:${AWS_ACCOUNT_ID}:key/mrk-51a95f6d174540158f3e0355608624f9"
		},
		{
			"Sid": "Logs",
			"Effect": "Allow",
			"Action": [
				"logs:CreateLogGroup",
				"logs:CreateLogStream",
				"logs:PutLogEvents"
			],
			"Resource": "arn:aws:logs:us-east-1:${AWS_ACCOUNT_ID}:*"
		}
	]
}