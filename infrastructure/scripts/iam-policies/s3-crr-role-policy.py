{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "ReadSourceReplicationConfig",
			"Effect": "Allow",
			"Action": [
				"s3:GetReplicationConfiguration",
				"s3:ListBucket"
			],
			"Resource": "arn:aws:s3:::kareem-img-proc-processed-${AWS_ACCOUNT_ID}-us-east-1-an"
		},
		{
			"Sid": "ReadSourceObjectVersions",
			"Effect": "Allow",
			"Action": [
				"s3:GetObjectVersionForReplication",
				"s3:GetObjectVersionAcl"
			],
			"Resource": "arn:aws:s3:::kareem-img-proc-processed-${AWS_ACCOUNT_ID}-us-east-1-an/*"
		},
		{
			"Sid": "WriteDestinationReplica",
			"Effect": "Allow",
			"Action": [
				"s3:ReplicateObject",
				"s3:ReplicateDelete"
			],
			"Resource": "arn:aws:s3:::kareem-img-proc-processed-secondary-${AWS_ACCOUNT_ID}-us-west-1-an/*"
		},
		{
			"Sid": "DecryptSourceObjects",
			"Effect": "Allow",
			"Action": [
				"kms:Decrypt"
			],
			"Resource": "arn:aws:kms:us-east-1:${AWS_ACCOUNT_ID}:key/mrk-51a95f6d174540158f3e0355608624f9"
		},
		{
			"Sid": "EncryptDestinationObjects",
			"Effect": "Allow",
			"Action": [
				"kms:Encrypt",
				"kms:GenerateDataKey"
			],
			"Resource": "arn:aws:kms:us-west-1:${AWS_ACCOUNT_ID}:key/3ba3682d-9ec6-4a5d-8338-5cd0aed3ff50"
		}
	]
}