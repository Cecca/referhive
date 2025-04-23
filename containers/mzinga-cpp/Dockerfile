FROM ubuntu:latest

WORKDIR /app

RUN apt-get update && apt-get install -y clang git cmake
RUN git clone https://github.com/jonthysell/MzingaCpp.git . \
    && mkdir build \
    && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && make

    
CMD ["/app/build/mzingacpp"]


