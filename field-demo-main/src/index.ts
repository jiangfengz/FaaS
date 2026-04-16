import { basekit, FieldType, field, FieldComponent, FieldCode, NumberFormatter, AuthorizationType } from '@lark-opdev/block-basekit-server-api';
const { t } = field;

// 添加API域名白名单 - 更新为云服务器地址
basekit.addDomainList(['119.45.114.53:6921', 'localhost:6921', 'api.example.com']);

basekit.addField({
  // 定义捷径的i18n语言资源
  i18n: {
    messages: {
      'zh-CN': {
        'api_key_label': 'API凭证绑定',
        'api_key_placeholder': '请输入您的API Key',
        'task_selection_label': '任务选择',
        'task_selection_placeholder': '请选择要执行的任务',
        'information_input_label': '信息输入',
        'information_input_placeholder': '请输入任务相关信息',
        'task_sentiment_analysis': '情感分析',
        'task_text_summarization': '文本摘要',
        'task_translation': '文本翻译',
        'task_entity_extraction': '实体提取',
        'success_message': '任务执行成功',
        'error_invalid_api_key': 'API凭证无效',
        'error_insufficient_balance': '余额不足',
        'error_task_failed': '任务执行失败',
        'error_network_error': '网络连接错误'
      },
      'en-US': {
        'api_key_label': 'API Key Binding',
        'api_key_placeholder': 'Please enter your API Key',
        'task_selection_label': 'Task Selection',
        'task_selection_placeholder': 'Please select a task to execute',
        'information_input_label': 'Information Input',
        'information_input_placeholder': 'Please enter task-related information',
        'task_sentiment_analysis': 'Sentiment Analysis',
        'task_text_summarization': 'Text Summarization',
        'task_translation': 'Text Translation',
        'task_entity_extraction': 'Entity Extraction',
        'success_message': 'Task executed successfully',
        'error_invalid_api_key': 'Invalid API Key',
        'error_insufficient_balance': 'Insufficient balance',
        'error_task_failed': 'Task execution failed',
        'error_network_error': 'Network connection error'
      },
      'ja-JP': {
        'api_key_label': 'API認証情報のバインド',
        'api_key_placeholder': 'API Keyを入力してください',
        'task_selection_label': 'タスク選択',
        'task_selection_placeholder': '実行するタスクを選択してください',
        'information_input_label': '情報入力',
        'information_input_placeholder': 'タスク関連の情報を入力してください',
        'task_sentiment_analysis': '感情分析',
        'task_text_summarization': 'テキスト要約',
        'task_translation': 'テキスト翻訳',
        'task_entity_extraction': 'エンティティ抽出',
        'success_message': 'タスクが正常に実行されました',
        'error_invalid_api_key': '無効なAPI Keyです',
        'error_insufficient_balance': '残高が不足しています',
        'error_task_failed': 'タスクの実行に失敗しました',
        'error_network_error': 'ネットワーク接続エラー'
      }
    }
  },
  
  // 定义捷径的入参表单
  formItems: [
    {
      key: 'api_key',
      label: t('api_key_label'),
      component: FieldComponent.Input,
      props: {
        placeholder: t('api_key_placeholder'),
        type: 'password' // 设置为密码类型，隐藏输入字符
      },
      validator: {
        required: true
        // 注意：字段捷径的validator不支持pattern验证
        // API Key格式验证需要在execute函数中实现
      }
    },
    {
      key: 'task_selection',
      label: t('task_selection_label'),
      component: FieldComponent.SingleSelect,
      props: {
        placeholder: t('task_selection_placeholder'),
        options: [
          { label: t('task_sentiment_analysis'), value: '情感分析' },
          { label: t('task_text_summarization'), value: '文本摘要' },
          { label: t('task_translation'), value: '翻译' },
          { label: t('task_entity_extraction'), value: '实体提取' }
        ]
      },
      validator: {
        required: true
      }
    },
    {
      key: 'information_input',
      label: t('information_input_label'),
      component: FieldComponent.Input,
      props: {
        placeholder: t('information_input_placeholder'),
        multiline: true, // 设置为多行文本输入
        rows: 4 // 设置文本域的行数
      },
      validator: {
        required: true,
        minLength: 1,
        maxLength: 5000 // 限制输入长度
      }
    }
  ],
  
  // 定义捷径的返回结果类型
  resultType: {
    type: FieldType.Object,
    extra: {
      icon: {
        light: 'https://lf3-static.bytednsdoc.com/obj/eden-cn/eqgeh7upeubqnulog/api-icon.svg',
      },
      properties: [
        {
          key: 'task_id',
          isGroupByKey: true,
          type: FieldType.Text,
          label: '任务ID',
          hidden: true,
        },
        {
          key: 'status',
          type: FieldType.Text,
          label: '执行状态',
          primary: true,
        },
        {
          key: 'result',
          type: FieldType.Text,
          label: '执行结果',
        },
        {
          key: 'execution_time',
          type: FieldType.Number,
          label: '执行时间(ms)',
          extra: {
            formatter: NumberFormatter.DIGITAL_ROUNDED_1,
          }
        },
        {
          key: 'error_message',
          type: FieldType.Text,
          label: '错误信息',
          hidden: true, // 正常情况下隐藏错误信息
        }
      ],
    },
  },
  
  // 执行函数 - 处理用户输入并调用API
  execute: async (formItemParams: {
    api_key: string;
    task_selection: { label: string; value: string };
    information_input: string;
  }, context) => {
    const { api_key, task_selection, information_input } = formItemParams;
    
    // 调试日志函数
    function debugLog(arg: any) {
      // @ts-ignore
      console.log(JSON.stringify({
        formItemParams,
        context,
        arg
      }))
    }
    
    const startTime = Date.now();
    
    try {
      debugLog({
        '===1 开始执行任务': {
          task: task_selection.value,
          input_length: information_input.length
        }
      });
      
      // 构建API请求参数 - 根据后端API格式调整
      const requestBody = {
        api_key_binding: api_key,           // 后端期望的参数名
        task_selection: task_selection.value, // 后端期望的参数名
        information_input: information_input  // 后端期望的参数名
      };
      
      debugLog({
        '===2 API请求参数': {
          task: task_selection.value,
          has_api_key: !!api_key,
          input_preview: information_input.substring(0, 100) + '...'
        }
      });
      
      // 直接调用云服务器后端API - 使用正确的端点
      const apiUrl = 'http://119.45.114.53:6921/api/chat'; // 云服务器后端服务地址，使用新的API端点
      
      // 调用后端API
      const response = await context.fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
          // 注意：后端不需要Bearer认证，API Key在请求体中传递
        },
        body: JSON.stringify(requestBody)
      });
      
      const responseText = await response.text();
      const executionTime = Date.now() - startTime;
      
      debugLog({
        '===3 API响应状态': {
          status: response.status,
          execution_time: executionTime
        }
      });
      
      if (!response.ok) {
        // 处理HTTP错误
        let errorMessage = t('error_task_failed');
        
        try {
          const errorData = JSON.parse(responseText);
          if (errorData.error) {
            errorMessage = errorData.error;
          }
        } catch (e) {
          // 如果无法解析错误信息，使用默认错误消息
        }
        
        // 根据HTTP状态码设置具体的错误信息
        if (response.status === 401) {
          errorMessage = t('error_invalid_api_key');
        } else if (response.status === 402) {
          errorMessage = t('error_insufficient_balance');
        } else if (response.status >= 500) {
          errorMessage = t('error_network_error');
        }
        
        return {
          code: FieldCode.Success, // 返回成功状态，但通过数据传递错误信息
          data: {
            task_id: `error_${Date.now()}`,
            status: '执行失败',
            result: errorMessage,
            execution_time: executionTime,
            error_message: errorMessage
          }
        };
      }
      
      // 解析成功响应
      let resultData;
      try {
        resultData = JSON.parse(responseText);
      } catch (e) {
        debugLog({
          '===4 响应解析错误': String(e)
        });
        
        return {
          code: FieldCode.Success,
          data: {
            task_id: `parse_error_${Date.now()}`,
            status: '执行失败',
            result: '响应数据格式错误',
            execution_time: executionTime,
            error_message: '无法解析API响应'
          }
        };
      }
      
      debugLog({
        '===5 任务执行成功': {
          success: resultData.success,
          result_length: resultData.result ? resultData.result.length : 0
        }
      });
      
      // 根据后端响应格式处理结果
      if (resultData.success) {
        // 任务执行成功
        return {
          code: FieldCode.Success,
          data: {
            task_id: `success_${Date.now()}`,
            status: '执行成功',
            result: resultData.result || t('success_message'),
            execution_time: executionTime,
            error_message: '' // 清空错误信息
          }
        };
      } else {
        // 任务执行失败
        return {
          code: FieldCode.Success,
          data: {
            task_id: `failed_${Date.now()}`,
            status: '执行失败',
            result: resultData.error || t('error_task_failed'),
            execution_time: executionTime,
            error_message: resultData.error || '任务执行失败'
          }
        };
      }
      
    } catch (error) {
      const executionTime = Date.now() - startTime;
      const errorMessage = String(error);
      
      debugLog({
        '===999 异常错误': errorMessage
      });
      
      // 处理网络错误和其他异常
      return {
        code: FieldCode.Success,
        data: {
          task_id: `exception_${Date.now()}`,
          status: '执行失败',
          result: t('error_network_error'),
          execution_time: executionTime,
          error_message: errorMessage
        }
      };
    }
  },
});

export default basekit;