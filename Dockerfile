FROM python:3.6-alpine3.7

# Create folder for source code and make it our working directory.
RUN mkdir -p /src
WORKDIR /src

# Install compilers and update the Python packages.
ADD requirements.txt .
RUN pip install -r requirements.txt

# Copy the repository into the container.
ADD . .
