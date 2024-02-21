import * as path from 'path';
import { Aws, CustomResource, Duration } from 'aws-cdk-lib';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { Code, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Size } from 'aws-cdk-lib/core';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

export interface ResourceProviderProps {
  bucketName?: string;
  version?: string;
}

export class ResourceProvider extends Construct {

  public readonly resources: CustomResource;
  public readonly role: Role;
  public readonly handler: NodejsFunction;
  public readonly provider: Provider;
  public readonly bucketName: string;

  constructor(scope: Construct, id: string, props: ResourceProviderProps) {
    super(scope, id);

    this.role = this.iamRole();


    const binaryLayer = new LayerVersion(this, 'ResourceManagerLayer', {
      code: Code.fromAsset(path.join(__dirname, 'resource-provider-layer.zip')),
      compatibleRuntimes: [Runtime.NODEJS_18_X],
      description: 'A layer that contains a s5cmd',
    });

    this.handler = new NodejsFunction(scope, 'ResourceManagerHandler', {
      runtime: Runtime.NODEJS_18_X,
      handler: 'handler',
      entry: 'src/shared/resource-provider-on-event.ts',
      bundling: {
        minify: true,
        externalModules: ['aws-cdk-lib'],
      },
      timeout: Duration.seconds(900),
      role: this.role,
      memorySize: 10240,
      ephemeralStorageSize: Size.gibibytes(10),
      layers: [binaryLayer],
      environment: {
        ROLE_ARN: this.role.roleArn,
        BUCKET_NAME: props.bucketName ?? '',
        ESD_VERSION: '1.4.0',
      },
    });

    this.provider = new Provider(scope, 'ResourceProvider', {
      onEventHandler: this.handler,
      logRetention: RetentionDays.ONE_DAY,
    });

    this.resources = new CustomResource(scope, 'ResourceManager', {
      serviceToken: this.provider.serviceToken,
      properties: props,
    });

    this.bucketName = this.resources.getAtt('BucketName').toString();

  }

  public instanceof(resource: any) {
    return [
      this,
      this.role,
      this.provider,
      this.handler,
      this.resources,
    ].includes(resource);
  }


  private iamRole(): Role {

    const newRole = new Role(this, 'deploy-check-role', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
    });

    newRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'dynamodb:CreateTable',
        'dynamodb:UpdateTable',
        'sns:CreateTopic',
        'iam:ListRolePolicies',
        'iam:PutRolePolicy',
        'sts:AssumeRole',
        'iam:GetRole',
        'kms:CreateKey',
        'kms:CreateAlias',
        'kms:DisableKeyRotation',
        'kms:ListAliases',
      ],
      resources: [
        '*',
      ],
    }));

    newRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        's3:ListBucket',
        's3:CreateBucket',
        's3:PutBucketCORS',
        's3:GetObject',
        's3:PutObject',
        's3:HeadObject',
        's3:DeleteObject',
        's3:GetBucketLocation',
      ],
      resources: [
        `arn:${Aws.PARTITION}:s3:::*`,
      ],
    }));

    newRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
        'kms:Decrypt',
      ],
      resources: ['*'],
    }));

    newRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'iam:PassRole',
      ],
      resources: [
        `arn:${Aws.PARTITION}:iam::${Aws.ACCOUNT_ID}:role/*`,
      ],
    }));

    return newRole;
  }

}
