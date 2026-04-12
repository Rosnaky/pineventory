# Pineventory

The Discord inventory management tool  

The goal of this application is to keep track of inventory in a team using Discord.

### Features

1) View and modify current inventory
2) Sign inventory out
3) Assign details about each product (location, size, point of contact)

### Deployment

Hosted on Azure as a Docker container deployment  

Create Docker container
```
az container create \
  --resource-group <rg-name> \
  --name pineventory \
  --image rosnaky/pineventory:latest \
  --cpu 1 --memory 1.5 \
  --ports 8080 \
  --secure-environment-variables \
    DISCORD_TOKEN="your-token" \
    DATABASE_URL="your-db-url" \
    GOOGLE_TOKEN_PATH="/app/config/google_token.json" \
  --azure-file-volume-account-name pineventorystorage \
  --azure-file-volume-account-key "your-key" \
  --azure-file-volume-share-name config \
  --azure-file-volume-mount-path /app/config
```

Deleting the container
```
az container delete --resource-group <rg-name> --name pineventory --yes
```

Show logs
```
az container logs --resource-group pineventory --name pineventory
```