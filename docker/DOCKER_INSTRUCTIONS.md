# Docker Setup Instructions

## Prerequisites
- Docker installed (https://www.docker.com/products/docker-desktop)
- Docker Compose installed (comes with Docker Desktop)

## Building the Image

From the project root directory:

```bash
docker build -f docker/Dockerfile -t soc-automation:1.0 .
```

## Running with Docker Compose

### Start the container:

```bash
cd docker
docker-compose up -d
```

### Check container status:

```bash
docker-compose ps
```

### View logs:

```bash
docker-compose logs -f
```

### Stop the container:

```bash
docker-compose down
```

## Running Directly with Docker

### Build the image:

```bash
docker build -f docker/Dockerfile -t soc-automation:1.0 .
```

### Run the container:

```bash
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --name soc-automation \
  soc-automation:1.0
```

### Access the dashboard:

Open browser: http://localhost:5000

### Stop the container:

```bash
docker stop soc-automation
docker rm soc-automation
```

## Docker Commands Reference

### View container logs:
```bash
docker logs soc-automation
```

### Execute commands in container:
```bash
docker exec -it soc-automation bash
```

### Check container health:
```bash
docker ps
```

### Remove image:
```bash
docker rmi soc-automation:1.0
```

## Troubleshooting

### Port 5000 already in use:
```bash
docker run -d -p 5001:5000 soc-automation:1.0
```
Then access at http://localhost:5001

### Container exits immediately:
```bash
docker logs soc-automation
```

### Database permissions:
Make sure `data/` and `logs/` directories are writable.

## Production Deployment

For production, consider:
1. Using a proper WSGI server (Gunicorn, uWSGI)
2. Adding environment configuration
3. Using Docker secrets for sensitive data
4. Setting resource limits
5. Adding monitoring and logging

## Kubernetes Deployment

To deploy to Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: soc-automation
spec:
  replicas: 2
  selector:
    matchLabels:
      app: soc-automation
  template:
    metadata:
      labels:
        app: soc-automation
    spec:
      containers:
      - name: soc-automation
        image: soc-automation:1.0
        ports:
        - containerPort: 5000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```