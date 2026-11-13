provider "aws" {
  region = var.aws_region
}

resource "aws_dynamodb_table" "events" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"

  attribute {
    name = "event_id"
    type = "S"
  }

  tags = {
    Project   = "cloud-reliability-platform"
    ManagedBy = "Terraform"
  }
}
