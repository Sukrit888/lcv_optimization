# Use a slim Python image for a smaller container size
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port that uvicorn will run on
EXPOSE 5000

# Command to run the application using uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "5000"]
