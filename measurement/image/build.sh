# build and push
#ansible all -m shell -a "docker rmi -f xxx/k8s-mxnet-measurement:latest"
#docker build -t xxx/k8s-mxnet-measurement:latest -f k8s-mxnet-measurement.Dockerfile .
#docker push xxx/k8s-mxnet-measurement:latest

docker rmi -f cogito288/k8s-mxnet-measurement:latest
docker build -t cogito288/k8s-mxnet-measurement:latest -f k8s-mxnet-measurement.Dockerfile .
docker push cogito288/k8s-mxnet-measurement:latest
