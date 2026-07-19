# R0.1 (D-172): Next.js requires Node >=20.9.0 — node:18 fails `next build` on a
# clean image build ("Node.js version >=20.9.0 is required"). Pin to node:20.
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source
COPY . .

# Build for production
RUN npm run build

# Expose port
EXPOSE 3000

# Start
CMD ["npm", "start"]
