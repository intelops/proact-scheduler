#Docker file to build a docker image for the application

FROM python:3.10-slim@sha256:2bac43769ace90ebd3ad83e5392295e25dfc58e58543d3ab326c3330b505283d

# Set the working directory in the container
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Install scsctl from test pypi
RUN pip install --no-cache-dir --index-url https://test.pypi.org/simple/ scsctl

# Copy the current directory contents into the container at /app
COPY . /app



EXPOSE 5000

# Run app.py when the container launches
CMD ["python", "src/proact_server/app.py"]