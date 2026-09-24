# IAM

Create six distinct roles with these exact trust principals:

| Role | Trust principal |
|---|---|
| ECS execution | `ecs-tasks.amazonaws.com` |
| API task | `ecs-tasks.amazonaws.com` |
| Projector | `lambda.amazonaws.com` |
| Relay | `lambda.amazonaws.com` |
| Archiver | `lambda.amazonaws.com` |
| Scheduler | `scheduler.amazonaws.com` |

Grant only the following access and scope every permission to the matching
resource:

| Role | Required access |
|---|---|
| ECS execution | `logs:CreateLogStream` and `logs:PutLogEvents` on the API log group. |
| API task | `sqs:SendMessage` and `sqs:GetQueueAttributes` on the main queue; `dynamodb:DescribeTable`, `dynamodb:GetItem` and `dynamodb:Query` on the projection table; `kms:Decrypt` and `kms:GenerateDataKey` on the messaging and projection keys. |
| Projector | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:ChangeMessageVisibility` and `sqs:GetQueueAttributes` on the main queue; `dynamodb:GetItem`, `dynamodb:PutItem` and `dynamodb:UpdateItem` on the projection table; `logs:CreateLogStream` and `logs:PutLogEvents` on the projector log group; `kms:Decrypt` and `kms:GenerateDataKey` on the messaging and projection keys; and the Lambda VPC actions below. |
| Relay | `sqs:SendMessage` and `sqs:GetQueueAttributes` on the main queue; `logs:CreateLogStream` and `logs:PutLogEvents` on the relay log group; `kms:Decrypt` and `kms:GenerateDataKey` on the messaging key; and the Lambda VPC actions below. |
| Archiver | `s3:PutObject` on objects under the configured audit prefix; `logs:CreateLogStream` and `logs:PutLogEvents` on the archiver log group; `kms:Encrypt` and `kms:GenerateDataKey` on the audit key; and the Lambda VPC actions below. |
| Scheduler | `lambda:InvokeFunction` on only the relay and archiver functions. |

Do not grant wildcard actions. Do not grant wildcard resources except for a
Lambda worker statement limited to these VPC actions:

- `ec2:CreateNetworkInterface`
- `ec2:DescribeNetworkInterfaces`
- `ec2:DeleteNetworkInterface`
- `ec2:DescribeSubnets`
- `ec2:AssignPrivateIpAddresses`
- `ec2:UnassignPrivateIpAddresses`
