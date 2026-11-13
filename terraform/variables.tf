variable "aws_region" {
  description = "AWS Region for a future deployment."
  type        = string
  default     = "us-east-1"
}

variable "table_name" {
  description = "Name of the DynamoDB events table."
  type        = string
  default     = "cloud_reliability_events"
}
