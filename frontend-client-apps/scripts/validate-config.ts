#!/usr/bin/env node
/**
 * Configuration validation script
 * Validates environment configuration for both speaker and listener apps
 * 
 * Usage:
 *   npm run validate-config
 *   npm run validate-config -- --app=speaker
 *   npm run validate-config -- --app=listener
 */

const fs = require('fs');
const path = require('path');

interface ValidationResult {
  app: string;
  valid: boolean;
  errors: string[];
  warnings: string[];
}

interface EnvVar {
  name: string;
  required: boolean;
  validator?: (value: string) => string | null; // Returns error message or null
}

const SPEAKER_ENV_VARS: EnvVar[] = [
  {
    name: 'VITE_WEBSOCKET_URL',
    required: true,
    validator: (value) => {
      if (!value.startsWith('wss://') && !value.startsWith('ws://')) {
        return 'Must start with wss:// or ws://';
      }
      try {
        new URL(value);
        return null;
      } catch {
        return 'Invalid URL format';
      }
    },
  },
  {
    name: 'VITE_COGNITO_USER_POOL_ID',
    required: true,
    validator: (value) => {
      if (!/^[a-z]+-[a-z]+-\d+_[a-zA-Z0-9]+$/.test(value)) {
        return 'Invalid Cognito User Pool ID format';
      }
      return null;
    },
  },
  {
    name: 'VITE_COGNITO_CLIENT_ID',
    required: true,
    validator: (value) => {
      if (value.length < 10) {
        return 'Client ID seems too short';
      }
      return null;
    },
  },
  {
    name: 'VITE_AWS_REGION',
    required: true,
    validator: (value) => {
      if (!/^[a-z]+-[a-z]+-\d+$/.test(value)) {
        return 'Invalid AWS region format (e.g., us-east-1)';
      }
      return null;
    },
  },
  {
    name: 'VITE_ENCRYPTION_KEY',
    required: true,
    validator: (value) => {
      if (value.length < 32) {
        return 'Must be at least 32 characters';
      }
      if (value === 'your-32-character-encryption-key-here') {
        return 'Please replace with a secure key (use: openssl rand -base64 32)';
      }
      if (value.includes('example') || value.includes('placeholder')) {
        return 'Please replace example/placeholder with a real key';
      }
      return null;
    },
  },
  {
    name: 'VITE_RUM_GUEST_ROLE_ARN',
    required: false,
  },
  {
    name: 'VITE_RUM_IDENTITY_POOL_ID',
    required: false,
  },
  {
    name: 'VITE_RUM_ENDPOINT',
    required: false,
  },
];

const LISTENER_ENV_VARS: EnvVar[] = [
  {
    name: 'VITE_WEBSOCKET_URL',
    required: true,
    validator: (value) => {
      if (!value.startsWith('wss://') && !value.startsWith('ws://')) {
        return 'Must start with wss:// or ws://';
      }
      try {
        new URL(value);
        return null;
      } catch {
        return 'Invalid URL format';
      }
    },
  },
  {
    name: 'VITE_AWS_REGION',
    required: true,
    validator: (value) => {
      if (!/^[a-z]+-[a-z]+-\d+$/.test(value)) {
        return 'Invalid AWS region format (e.g., us-east-1)';
      }
      return null;
    },
  },
  {
    name: 'VITE_ENCRYPTION_KEY',
    required: true,
    validator: (value) => {
      if (value.length < 32) {
        return 'Must be at least 32 characters';
      }
      if (value === 'your-32-character-encryption-key-here') {
        return 'Please replace with a secure key (use: openssl rand -base64 32)';
      }
      if (value.includes('example') || value.includes('placeholder')) {
        return 'Please replace example/placeholder with a real key';
      }
      return null;
    },
  },
  {
    name: 'VITE_RUM_GUEST_ROLE_ARN',
    required: false,
  },
  {
    name: 'VITE_RUM_IDENTITY_POOL_ID',
    required: false,
  },
  {
    name: 'VITE_RUM_ENDPOINT',
    required: false,
  },
];

function parseEnvFile(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) {
    return {};
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const env: Record<string, string> = {};

  content.split('\n').forEach((line: string) => {
    // Skip comments and empty lines
    if (line.trim().startsWith('#') || !line.trim()) {
      return;
    }

    const match = line.match(/^([^=]+)=(.*)$/);
    if (match) {
      const key = match[1].trim();
      const value = match[2].trim();
      env[key] = value;
    }
  });

  return env;
}

function validateApp(appName: string, envVars: EnvVar[]): ValidationResult {
  const result: ValidationResult = {
    app: appName,
    valid: true,
    errors: [],
    warnings: [],
  };

  const envPath = path.join(__dirname, '..', `${appName}-app`, '.env');
  const examplePath = path.join(__dirname, '..', `${appName}-app`, '.env.example');

  // Check if .env file exists
  if (!fs.existsSync(envPath)) {
    result.valid = false;
    result.errors.push(`.env file not found at ${envPath}`);
    result.warnings.push(`Copy .env.example to .env: cp ${examplePath} ${envPath}`);
    return result;
  }

  const env = parseEnvFile(envPath);

  // Validate each environment variable
  envVars.forEach((envVar) => {
    const value = env[envVar.name];

    if (envVar.required && !value) {
      result.valid = false;
      result.errors.push(`${envVar.name} is required but not set`);
      return;
    }

    if (value && envVar.validator) {
      const error = envVar.validator(value);
      if (error) {
        result.valid = false;
        result.errors.push(`${envVar.name}: ${error}`);
      }
    }

    // Check for optional RUM configuration
    if (!envVar.required && !value) {
      if (envVar.name.startsWith('VITE_RUM_')) {
        // Only warn if some RUM vars are set but not all
        const rumVars = envVars.filter((v) => v.name.startsWith('VITE_RUM_'));
        const setRumVars = rumVars.filter((v) => env[v.name]);
        if (setRumVars.length > 0 && setRumVars.length < rumVars.length) {
          result.warnings.push(
            `${envVar.name} is not set. RUM monitoring requires all RUM variables.`
          );
        }
      }
    }
  });

  return result;
}

function printResult(result: ValidationResult): void {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`${result.app.toUpperCase()} APP CONFIGURATION`);
  console.log('='.repeat(60));

  if (result.valid) {
    console.log('✅ Configuration is valid!');
  } else {
    console.log('❌ Configuration has errors!');
  }

  if (result.errors.length > 0) {
    console.log('\n🔴 ERRORS:');
    result.errors.forEach((error) => {
      console.log(`   - ${error}`);
    });
  }

  if (result.warnings.length > 0) {
    console.log('\n⚠️  WARNINGS:');
    result.warnings.forEach((warning) => {
      console.log(`   - ${warning}`);
    });
  }

  console.log('');
}

function main(): void {
  const args = process.argv.slice(2);
  const appArg = args.find((arg) => arg.startsWith('--app='));
  const targetApp = appArg ? appArg.split('=')[1] : null;

  console.log('🔍 Frontend Configuration Validator\n');

  const results: ValidationResult[] = [];

  if (!targetApp || targetApp === 'speaker') {
    results.push(validateApp('speaker', SPEAKER_ENV_VARS));
  }

  if (!targetApp || targetApp === 'listener') {
    results.push(validateApp('listener', LISTENER_ENV_VARS));
  }

  results.forEach(printResult);

  // Summary
  console.log('='.repeat(60));
  console.log('SUMMARY');
  console.log('='.repeat(60));

  const allValid = results.every((r) => r.valid);
  const totalErrors = results.reduce((sum, r) => sum + r.errors.length, 0);
  const totalWarnings = results.reduce((sum, r) => sum + r.warnings.length, 0);

  console.log(`Apps validated: ${results.length}`);
  console.log(`Total errors: ${totalErrors}`);
  console.log(`Total warnings: ${totalWarnings}`);

  if (allValid) {
    console.log('\n✅ All configurations are valid!');
    console.log('\nNext steps:');
    console.log('  1. Run: npm run build:all');
    console.log('  2. Test: npm run dev:speaker (in one terminal)');
    console.log('  3. Test: npm run dev:listener (in another terminal)');
  } else {
    console.log('\n❌ Please fix the errors above before proceeding.');
    console.log('\nFor help, see: CONFIGURATION_GUIDE.md');
    process.exit(1);
  }

  console.log('');
}

main();
