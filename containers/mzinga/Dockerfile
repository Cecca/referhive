# Use the official .NET image as the base image
FROM mcr.microsoft.com/dotnet/sdk:7.0 AS build-env

# Set the working directory
WORKDIR /app

# Copy the Mzinga source code into the container
# (Assumes the context includes the Mzinga source code)
# COPY . ./
RUN apt-get update && apt-get install -y wget unzip \
    && wget https://github.com/jonthysell/Mzinga/releases/download/v0.15.1/Mzinga.LinuxX64.tar.gz -O Mzinga_Linux.zip \
    && tar xvf Mzinga_Linux.zip -C /app --strip-components=1 \
    && rm Mzinga_Linux.zip

# RUN cd Mzinga.Linux

# Specify the entry point for the container
CMD ["/app/MzingaEngine"]
