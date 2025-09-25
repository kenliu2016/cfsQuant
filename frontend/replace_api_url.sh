#!/bin/sh

# Script to replace the API base URL in the built frontend files

# Check if API_BASE_URL is set
if [ -z "$API_BASE_URL" ]; then
  echo "API_BASE_URL is not set, using default value"
  API_BASE_URL="http://localhost:8000/api"
fi

# Find all JavaScript and HTML files and replace the placeholder with the actual API URL
echo "Replacing API base URL with $API_BASE_URL"
find /usr/share/nginx/html -type f \( -name "*.js" -o -name "*.html" \) -exec sed -i "s|http://localhost:8000/api|$API_BASE_URL|g" {} \;

# Also replace the VITE_API_BASE_URL placeholder
find /usr/share/nginx/html -type f \( -name "*.js" -o -name "*.html" \) -exec sed -i "s|VITE_API_BASE_URL|$API_BASE_URL|g" {} \;

echo "API URL replacement completed"