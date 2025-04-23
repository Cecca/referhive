build-all:
    just build-container mzinga
    just build-container mzinga-cpp
    just build-container nokamute

run-container name:
    just build-container {{name}}
    docker run -it --rm -w /app {{name}}

build-container name:
    docker build -t {{name}} containers/{{name}}
