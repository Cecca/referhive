# Use an official Rust image as the base
FROM rust:latest

WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/edre/nokamute.git .
RUN cargo build --release
CMD ["./target/release/nokamute"]
