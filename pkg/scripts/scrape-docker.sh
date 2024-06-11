#!/bin/bash

# Function to stop and remove a container with a specific name
cleanup_specific_container() {
  container_name=$1
  container_id=$(docker ps -aqf "name=${container_name}")

  if [ -n "$container_id" ]; then
    echo "Stopping container: $container_name..."
    docker stop $container_name

    echo "Removing container: $container_name..."
    docker rm $container_name
  else
    echo "No container found with the name: $container_name"
  fi
}

# Function to run a specific Docker container
run_container() {
  container_name=$1
  
  docker run -d \
    --name $container_name \
    -v /home/ubuntu/FYP-RentInSG/pkg/logs/scraper:/app/pkg/logs/scraper \
    -v /home/ubuntu/FYP-RentInSG/pkg/rental_prices/ninety_nine:/app/pkg/rental_prices/ninety_nine \
    rowentey/fyp-rent-in-sg:99co-scraper-latest
}

# Main script execution
container_name="99co-scraper" 

echo "Cleaning up container: $container_name..."
cleanup_specific_container $container_name

echo "Running the specific Docker container..."
run_container $container_name

echo "Done."