run-nokamute-container: build-nokamute-container
    docker run -it --rm -w /app nokamute

build-nokamute-container:
    docker build -t nokamute containers/nokamute

run-mzinga-container: build-mzinga-container
    docker run -it --rm -w /app mzinga 

build-mzinga-container:
    docker build -t mzinga containers/mzinga
