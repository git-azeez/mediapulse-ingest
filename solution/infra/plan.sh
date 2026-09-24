#!/bin/bash
export TF_LOG=TRACE
export TF_LOG_PATH=tf.log
export HTTP_PROXY="http://172.20.0.1:18080"
export HTTPS_PROXY="http://172.20.0.1:18080"
export NO_PROXY="localhost,127.0.0.1,gcp"
terraform apply -auto-approve
