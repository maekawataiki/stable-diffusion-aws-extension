拡張機能の全体的なアーキテクチャは、拡張機能とミドルウェアの2つのコンポーネントで構成されています。拡張機能は、コミュニティの WebUI にインストールされ、ユーザーがミドルウェアと対話するためのユーザーインターフェイスを提供する役割を担っています。ミドルウェアは、ユーザーの AWS アカウントにデプロイされた AWS リソースの集合体であり、拡張機能が AWS リソースと対話するための RESTfulAPI を提供する役割を担っています。この全体的なソリューションにより、ユーザーは AWS でモデルの学習とデプロイを以下の機能を活用しながら、シームレスな体験ができるようになります:

- **ユーザー体験**: 既存の作業フローは変更されず、ユーザーはコミュニティの WebUI を使ってサードパーティの拡張機能でモデルの学習とデプロイを行うことができます。
- **スケーラビリティ**: 学習や推論などの既存の負荷を、Amazon SageMaker でより簡単に拡張したり高速化したりできます。
- **コミュニティ**: 提供される拡張機能はオープンソースのコミュニティ WebUI の一部であり、コミュニティと共に進化し続けます。
