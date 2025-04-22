run-mzinga-container: build-mzinga-container
    docker run -it --rm -w /app mzinga 

build-mzinga-container:
    docker build -t mzinga containers/mzinga
