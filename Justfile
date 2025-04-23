run-container name:
    just build-container {{name}}
    docker run -it --rm -w /app {{name}}

build-container name:
    docker build -t {{name}} containers/{{name}}
