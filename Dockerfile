#Docker file to build a docker image for the application

FROM python:3.10-slim@sha256:2bac43769ace90ebd3ad83e5392295e25dfc58e58543d3ab326c3330b505283d

# Set the working directory in the container
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt


RUN apt-get -y update; apt-get -y install curl

# Install Git
RUN apt-get install -y git

# Install Trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Install scsctl from test pypi
RUN pip install --no-cache-dir --index-url https://test.pypi.org/simple/ scsctl==0.0.6.11

# Copy the current directory contents into the container at /app
COPY . /app



EXPOSE 5000

# Run app.py when the container launches
CMD ["python", "src/proact_server/app.py"]
