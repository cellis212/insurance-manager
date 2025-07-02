FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install dependencies based on the preferred package manager
COPY package.json package-lock.json* ./
RUN npm ci

# Copy application code
COPY . .

# Disable Next.js telemetry during build
ENV NEXT_TELEMETRY_DISABLED 1

# Build the application (for production)
# RUN npm run build

# Expose port
EXPOSE 3000

# Run the development server (overridden in docker-compose.yml)
CMD ["npm", "run", "dev"] 