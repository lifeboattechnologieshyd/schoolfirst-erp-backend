# SchoolFirst ERP Backend

## Build Image

`docker buildx build --platform linux/amd64,linux/arm64 -t schoolfirst-erp-backend:latest --push .`

## Push Image

`docker push schoolfirst-erp-backend:latest`

## Build and Push

`docker buildx build --platform linux/amd64,linux/arm64 -t schoolfirst-erp-backend:latest --push .`

## Pull Image

`docker pull schoolfirst-erp-backend:latest`
