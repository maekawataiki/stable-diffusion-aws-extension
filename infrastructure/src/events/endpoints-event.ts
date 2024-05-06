import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { aws_iam, aws_lambda, Duration } from 'aws-cdk-lib';
import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { Rule } from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { Architecture, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import {NodejsFunction} from "aws-cdk-lib/aws-lambda-nodejs";

export interface SagemakerEndpointEventsProps {
  endpointDeploymentTable: Table;
  multiUserTable: Table;
  commonLayer: LayerVersion;
  logSubFn: NodejsFunction;
}

export class SagemakerEndpointEvents {
  private readonly scope: Construct;
  private readonly endpointDeploymentTable: Table;
  private readonly multiUserTable: Table;
  private readonly layer: LayerVersion;
  private readonly baseId: string;
  private readonly logSubFn: NodejsFunction;

  constructor(scope: Construct, id: string, props: SagemakerEndpointEventsProps) {
    this.scope = scope;
    this.baseId = id;
    this.endpointDeploymentTable = props.endpointDeploymentTable;
    this.multiUserTable = props.multiUserTable;
    this.layer = props.commonLayer;
    this.logSubFn = props.logSubFn;

    this.createEndpointEventBridge();
  }

  private iamRole(): Role {

    const newRole = new Role(this.scope, `${this.baseId}-role`, {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
    });

    newRole.addToPolicy(new aws_iam.PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'dynamodb:UpdateItem',
        'dynamodb:Query',
        'dynamodb:GetItem',
        'dynamodb:DeleteItem',
      ],
      resources: [
        this.endpointDeploymentTable.tableArn,
        `${this.endpointDeploymentTable.tableArn}/*`,
        this.multiUserTable.tableArn,
      ],
    }));

    newRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'sagemaker:DeleteModel',
        'sagemaker:DeleteEndpoint',
        'sagemaker:DeleteEndpointConfig',
        'sagemaker:DescribeEndpoint',
        'sagemaker:DescribeEndpointConfig',
        'sagemaker:UpdateEndpointWeightsAndCapacities',
        'cloudwatch:DeleteAlarms',
        'cloudwatch:DescribeAlarms',
        'cloudwatch:PutMetricAlarm',
        'cloudwatch:PutMetricData',
        'cloudwatch:UpdateMetricAlarm',
        'application-autoscaling:PutScalingPolicy',
        'application-autoscaling:RegisterScalableTarget',
        'iam:CreateServiceLinkedRole',
      ],
      resources: ['*'],
    }));

    newRole.addToPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
        'logs:PutSubscriptionFilter',
        'logs:DescribeSubscriptionFilters',
        'logs:DeleteLogGroup',
      ],
      resources: ['*'],
    }));

    return newRole;
  }

  private createEndpointEventBridge() {

    const lambdaFunction = new PythonFunction(this.scope, `${this.baseId}-lambda`, {
      entry: '../middleware_api/endpoints',
      architecture: Architecture.X86_64,
      runtime: Runtime.PYTHON_3_10,
      index: 'endpoint_event.py',
      handler: 'handler',
      timeout: Duration.seconds(900),
      role: this.iamRole(),
      memorySize: 3070,
      tracing: aws_lambda.Tracing.ACTIVE,
      layers: [this.layer],
      environment: {
        LOG_SUB_FN: this.logSubFn.functionArn,
      }
    });

    const rule = new Rule(this.scope, `${this.baseId}-rule`, {
      eventPattern: {
        source: ['aws.sagemaker'],
        detailType: ['SageMaker Endpoint State Change'],
      },
    });

    rule.addTarget(new LambdaFunction(lambdaFunction));

  }
}
