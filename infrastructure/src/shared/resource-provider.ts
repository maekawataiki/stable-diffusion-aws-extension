import { CustomResource, Duration } from 'aws-cdk-lib';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { Runtime } from 'aws-cdk-lib/aws-lambda';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';


export class ResourceProvider extends Construct {

  public readonly resources: CustomResource;
  public readonly role: Role;
  public readonly handler: NodejsFunction;
  public readonly provider: Provider;

  constructor(scope: Construct, id: string, bucketName: string) {
    super(scope, id);

    this.role = this.iamRole();

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
      memorySize: 4048,
    });

    this.provider = new Provider(scope, 'ResourceProvider', {
      onEventHandler: this.handler,
      logRetention: RetentionDays.ONE_DAY,
    });

    this.resources = new CustomResource(scope, 'ResourceManager', {
      serviceToken: this.provider.serviceToken,
      properties: { bucketName },
    });

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
        'sns:CreateTopic',
        'iam:ListRolePolicies',
        'iam:PutRolePolicy',
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
      ],
      resources: [
        'arn:aws:s3:::*',
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

    return newRole;
  }

}
