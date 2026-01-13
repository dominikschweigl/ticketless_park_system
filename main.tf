terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH access"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for all nodes"
  type        = string
  default     = "t3.micro"
}

variable "webapp_dist_path" {
  description = "Local path to the built webapp dist folder"
  type        = string
  default     = "src/ticketless_parking_system/webapp/dist"
}

variable "akka_jar_path" {
  description = "Local path to the built Akka JAR file"
  type        = string
  default     = "src/ticketless_parking_system/cloud/target/parking-system.jar"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_security_group" "parking_sg" {
  name        = "parking-system-sg"
  description = "Allow HTTP, Akka API, NATS, SSH"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Akka/HTTP app (8080)"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "NATS client"
    from_port   = 4222
    to_port     = 4222
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "NATS monitoring"
    from_port   = 8222
    to_port     = 8222
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "parking-system-sg"
  }
}

locals {
  common_tags = {
    Project = "ticketless-parking"
  }
}

resource "aws_instance" "akka_app" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.parking_sg.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              set -xe
              dnf update -y
              dnf install -y java-17-amazon-corretto-headless
              mkdir -p /opt/akka-app
              EOF

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = file("~/.ssh/${var.key_name}.pem")
    host        = self.public_ip
  }

  provisioner "file" {
    source      = var.akka_jar_path
    destination = "/tmp/parking-system.jar"
  }

  provisioner "remote-exec" {
    inline = [
      "timeout 120 bash -c 'until [ -f /tmp/parking-system.jar ]; do sleep 2; done'",
      "sudo mkdir -p /opt/akka-app",
      "sudo mv /tmp/parking-system.jar /opt/akka-app/parking-system.jar",
      "sudo chown root:root /opt/akka-app/parking-system.jar",
      <<-EOT
      sudo cat > /tmp/parking-system.service <<'SVCEOF'
      [Unit]
      Description=Parking System Akka Application
      After=network.target

      [Service]
      Type=simple
      User=ec2-user
      WorkingDirectory=/opt/akka-app
      Environment="NATS_URL=nats://${aws_instance.nats.private_ip}:4222"
      Environment="HTTP_HOST=0.0.0.0"
      Environment="HTTP_PORT=8080"
      ExecStart=/usr/bin/java -jar /opt/akka-app/parking-system.jar
      Restart=always
      RestartSec=10

      [Install]
      WantedBy=multi-user.target
      SVCEOF
      EOT
      ,
      "sudo mv /tmp/parking-system.service /etc/systemd/system/parking-system.service",
      "sudo systemctl daemon-reload",
      "sudo systemctl enable parking-system",
      "sudo systemctl start parking-system"
    ]
  }

  tags = merge(local.common_tags, { Name = "akka-app" })
}

resource "aws_instance" "nats" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.parking_sg.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              set -xe
              dnf update -y
              dnf install -y docker
              systemctl enable docker
              systemctl start docker
              docker run -d --name nats --restart=always -p 4222:4222 -p 8222:8222 nats:2.10-alpine -m 8222
              EOF

  tags = merge(local.common_tags, { Name = "nats" })
}

resource "aws_instance" "webapp" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.parking_sg.id]
  key_name                    = var.key_name
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              set -xe
              dnf update -y
              dnf install -y nginx
              systemctl enable nginx
              rm -rf /usr/share/nginx/html/*
              EOF

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = file("~/.ssh/${var.key_name}.pem")
    host        = self.public_ip
  }

  provisioner "remote-exec" {
    inline = [
      "mkdir -p /tmp/webapp",
      "echo 'Waiting for nginx installation...'",
      "timeout 300 bash -c 'until systemctl is-active nginx; do sleep 5; done'",
      "echo 'Nginx is ready'"
    ]
  }

  provisioner "file" {
    source      = "${var.webapp_dist_path}/"
    destination = "/tmp/webapp"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo rm -rf /usr/share/nginx/html/*",
      "sudo cp -r /tmp/webapp/* /usr/share/nginx/html/",
      "sudo chown -R nginx:nginx /usr/share/nginx/html",
      
      # ✅ Add runtime config.js for frontend to know Akka backend URL
      <<-EOT
      sudo tee /usr/share/nginx/html/config.js > /dev/null <<EOF
      window.APP_CONFIG = { API_BASE_URL: "http://${aws_instance.akka_app.public_ip}:8080" };
      EOF
      EOT
      ,
      "sudo systemctl restart nginx"
    ]
  }

  tags = merge(local.common_tags, { Name = "webapp" })
}

output "akka_app_public_ip" {
  value = aws_instance.akka_app.public_ip
}

output "nats_public_ip" {
  value = aws_instance.nats.public_ip
}

output "webapp_public_ip" {
  value = aws_instance.webapp.public_ip
}
