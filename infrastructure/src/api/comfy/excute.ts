import { PythonFunction, PythonFunctionProps } from '@aws-cdk/aws-lambda-python-alpha';
import {
  Aws,
  aws_apigateway,
  aws_apigateway as apigw,
  aws_dynamodb,
  aws_iam,
  aws_lambda,
  aws_sqs,
  CfnParameter,
  Duration,
} from 'aws-cdk-lib';
import { JsonSchemaType, JsonSchemaVersion, Model, RequestValidator } from 'aws-cdk-lib/aws-apigateway';
import { MethodOptions } from 'aws-cdk-lib/aws-apigateway/lib/method';
import { Effect } from 'aws-cdk-lib/aws-iam';
import { Architecture, Runtime } from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';


export interface ExecuteApiProps {
  httpMethod: string;
  router: aws_apigateway.Resource;
  srcRoot: string;
  s3Bucket: s3.Bucket;
  configTable: aws_dynamodb.Table;
  executeTable: aws_dynamodb.Table;
  endpointTable: aws_dynamodb.Table;
  modelTable: aws_dynamodb.Table;
  nodeTable: aws_dynamodb.Table;
  queue: aws_sqs.Queue;
  commonLayer: aws_lambda.LayerVersion;
  logLevel: CfnParameter;
}

export class ExecuteApi {
  private readonly baseId: string;
  private readonly srcRoot: string;
  private readonly router: aws_apigateway.Resource;
  private readonly httpMethod: string;
  private readonly scope: Construct;
  private readonly layer: aws_lambda.LayerVersion;
  private readonly logLevel: CfnParameter;
  private readonly s3Bucket: s3.Bucket;
  private readonly configTable: aws_dynamodb.Table;
  private readonly executeTable: aws_dynamodb.Table;
  private readonly endpointTable: aws_dynamodb.Table;
  private readonly modelTable: aws_dynamodb.Table;
  private readonly nodeTable: aws_dynamodb.Table;
  private queue: aws_sqs.Queue;

  constructor(scope: Construct, id: string, props: ExecuteApiProps) {
    this.scope = scope;
    this.httpMethod = props.httpMethod;
    this.baseId = id;
    this.router = props.router;
    this.srcRoot = props.srcRoot;
    this.s3Bucket = props.s3Bucket;
    this.configTable = props.configTable;
    this.executeTable = props.executeTable;
    this.endpointTable = props.endpointTable;
    this.modelTable = props.modelTable;
    this.nodeTable = props.nodeTable;
    this.layer = props.commonLayer;
    this.logLevel = props.logLevel;
    this.queue = props.queue;

    this.executeApi();
  }

  private iamRole(): aws_iam.Role {
    const newRole = new aws_iam.Role(this.scope, `${this.baseId}-role`, {
      assumedBy: new aws_iam.ServicePrincipal('lambda.amazonaws.com'),
    });
    newRole.addToPolicy(new aws_iam.PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'dynamodb:BatchGetItem',
        'dynamodb:GetItem',
        'dynamodb:Scan',
        'dynamodb:Query',
        'dynamodb:BatchWriteItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:DeleteItem',
      ],
      resources: [
        this.endpointTable.tableArn,
        this.modelTable.tableArn,
        this.nodeTable.tableArn,
        this.configTable.tableArn,
        this.executeTable.tableArn,
      ],
    }));

    newRole.addToPolicy(new aws_iam.PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'sagemaker:InvokeEndpointAsync',
        'sagemaker:InvokeEndpoint',
      ],
      resources: [`arn:${Aws.PARTITION}:sagemaker:${Aws.REGION}:${Aws.ACCOUNT_ID}:endpoint/*`],
    }));

    newRole.addToPolicy(new aws_iam.PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
        's3:CreateBucket',
      ],
      resources: [
        `${this.s3Bucket.bucketArn}/*`,
        `${this.s3Bucket.bucketArn}`,
      ],
    }));

    newRole.addToPolicy(new aws_iam.PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
      ],
      resources: ['*'],
    }));

    newRole.addToPolicy(new aws_iam.PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'sqs:SendMessage',
      ],
      resources: [this.queue.queueArn],
    }));
    return newRole;
  }

  private executeApi() {
    const lambdaFunction = new PythonFunction(this.scope, `${this.baseId}-lambda`, <PythonFunctionProps>{
      entry: `${this.srcRoot}/comfy`,
      architecture: Architecture.X86_64,
      runtime: Runtime.PYTHON_3_9,
      index: 'execute.py',
      handler: 'handler',
      timeout: Duration.seconds(900),
      role: this.iamRole(),
      memorySize: 1024,
      environment: {
        EXECUTE_TABLE: this.executeTable.tableName,
        MODEL_TABLE: this.modelTable.tableName,
        NODE_TABLE: this.nodeTable.tableName,
        CONFIG_TABLE: this.configTable.tableName,
        ENDPOINT_TABLE: this.endpointTable.tableName,
        SQS_URL: this.queue.queueUrl,
        BUCKET_NAME: this.s3Bucket.bucketName,
        LOG_LEVEL: this.logLevel.valueAsString,
      },
      layers: [this.layer],
    });

    const requestModel = new Model(this.scope, `${this.baseId}-model`, {
      restApi: this.router.api,
      modelName: this.baseId,
      description: `${this.baseId} Request Model`,
      schema: {
        schema: JsonSchemaVersion.DRAFT4,
        title: this.baseId,
        type: JsonSchemaType.OBJECT,
        properties: {
          prompt_id: {
            type: JsonSchemaType.STRING,
            minLength: 1,
          },
          prompt: {
            type: JsonSchemaType.OBJECT,
            minItems: 1,
            additionalProperties: true,
          },
          endpoint_name: {
            type: JsonSchemaType.STRING,
            minLength: 1,
          },
          need_sync: {
            type: JsonSchemaType.BOOLEAN,
            minLength: 1,
          },
          need_prepare: {
            type: JsonSchemaType.BOOLEAN,
            minLength: 1,
          },
          number: {
            type: JsonSchemaType.STRING,
            minLength: 1,
          },
          front: {
            type: JsonSchemaType.BOOLEAN,
            minLength: 1,
          },
          extra_data: {
            type: JsonSchemaType.OBJECT,
            minLength: 1,
            additionalProperties: true,
          },
          client_id: {
            type: JsonSchemaType.STRING,
            minLength: 1,
          },
        },
        required: [
          'prompt_id',
          'prompt',
          'endpoint_name',
          'need_prepare',
          'need_sync',
        ],
      },
      contentType: 'application/json',
    });

    const requestValidator = new RequestValidator(
      this.scope,
      `${this.baseId}-validator`,
      {
        restApi: this.router.api,
        validateRequestBody: true,
      });

    const lambdaIntegration = new apigw.LambdaIntegration(
      lambdaFunction,
      {
        proxy: true,
      },
    );
    this.router.addMethod(this.httpMethod, lambdaIntegration, <MethodOptions>{
      apiKeyRequired: true,
      requestValidator,
      requestModels: {
        'application/json': requestModel,
      },
    });
  }
}

