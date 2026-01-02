# Multi-stage build for AWS ECS deployment
# Stage 1: Build
FROM maven:3.8.6-eclipse-temurin-11 AS builder

WORKDIR /build
COPY pom.xml .
COPY src/ ./src/

RUN mvn clean package -DskipTests

# Stage 2: Runtime
FROM eclipse-temurin:11-jre-alpine

WORKDIR /app

# Copy the fat JAR from builder
COPY --from=builder /build/target/parking-system.jar ./parking-system.jar

# Create non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# Health check for ECS task monitoring
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Set environment variables
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"
ENV PARKING_ENVIRONMENT="production"

EXPOSE 8080

# Run the application
CMD ["sh", "-c", "java $JAVA_OPTS -jar parking-system.jar"]
