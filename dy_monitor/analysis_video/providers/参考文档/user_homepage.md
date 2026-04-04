# 获取用户主页作品数据/Get user homepage video data

## OpenAPI Specification

```yaml
openapi: 3.0.1
info:
  title: ''
  description: ''
  version: 1.0.0
paths:
  /api/v1/douyin/app/v3/fetch_user_post_videos:
    get:
      summary: 获取用户主页作品数据/Get user homepage video data
      deprecated: false
      description: >-
        # [中文]

        ### 用途:

        - 获取用户主页作品数据

        ### 参数:

        - sec_user_id: 用户sec_user_id

        - max_cursor: 最大游标，用于翻页，第一页为0，第二页为第一次响应中的max_cursor值。

        - count: 最大数量，不要超过20，建议保持不变。

        - sort_type: 排序类型，可选值如下：
            - `0`: 最新排序-默认
            - `1`: 最热排序
        ### 返回:

        - 用户作品数据


        # [English]

        ### Purpose:

        - Get user homepage video data

        ### Parameters:

        - sec_user_id: User sec_user_id

        - max_cursor: Maximum cursor, used for paging, the first page is 0, the
        second page is the max_cursor value in the first response.

        - count: Maximum count number, do not exceed 20, it is recommended to
        keep it unchanged.

        - sort_type: Sort type, optional values are as follows:
            - `0`: Latest sorting - default
            - `1`: Hottest sorting
        ### Return:

        - User video data


        # [示例/Example]

        sec_user_id = "MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE"

        max_cursor = 0

        counts = 20

        sort_type = 0
      operationId: fetch_user_post_videos_api_v1_douyin_app_v3_fetch_user_post_videos_get
      tags:
        - Douyin-App-V3-API
        - Douyin-App-V3-API
      parameters:
        - name: sec_user_id
          in: query
          description: 用户sec_user_id/User sec_user_id
          required: true
          example: MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE
          schema:
            type: string
            description: 用户sec_user_id/User sec_user_id
            title: Sec User Id
        - name: max_cursor
          in: query
          description: 最大游标/Maximum cursor
          required: false
          schema:
            type: integer
            description: 最大游标/Maximum cursor
            default: 0
            title: Max Cursor
        - name: count
          in: query
          description: 每页数量/Number per page
          required: false
          schema:
            type: integer
            description: 每页数量/Number per page
            default: 20
            title: Count
        - name: sort_type
          in: query
          description: 排序类型/Sort type
          required: false
          schema:
            type: integer
            description: 排序类型/Sort type
            default: 0
            title: Sort Type
      responses:
        '200':
          description: Successful Response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResponseModel'
          headers: {}
          x-apifox-name: OK
        '422':
          description: Validation Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HTTPValidationError'
          headers: {}
          x-apifox-name: Parameter Error
      security:
        - HTTPBearer: []
          x-apifox:
            schemeGroups:
              - id: 0YpHwwpFDBlVy7mCaNFAr
                schemeIds:
                  - HTTPBearer
            required: true
            use:
              id: 0YpHwwpFDBlVy7mCaNFAr
            scopes:
              0YpHwwpFDBlVy7mCaNFAr:
                HTTPBearer: []
      x-apifox-folder: Douyin-App-V3-API
      x-apifox-status: released
      x-run-in-apifox: https://app.apifox.com/web/project/4705614/apis/api-186826223-run
components:
  schemas:
    ResponseModel:
      properties:
        code:
          type: integer
          title: Code
          description: HTTP status code | HTTP状态码
          default: 200
        request_id:
          anyOf:
            - type: string
            - type: 'null'
          title: Request Id
          description: Unique request identifier | 唯一请求标识符
        message:
          type: string
          title: Message
          description: Response message (EN-US) | 响应消息 (English)
          default: Request successful. This request will incur a charge.
        message_zh:
          type: string
          title: Message Zh
          description: Response message (ZH-CN) | 响应消息 (中文)
          default: 请求成功，本次请求将被计费。
        support:
          type: string
          title: Support
          description: Support message | 支持消息
          default: 'Discord: https://discord.gg/aMEAS8Xsvz'
        time:
          type: string
          title: Time
          description: The time the response was generated | 生成响应的时间
        time_stamp:
          type: integer
          title: Time Stamp
          description: The timestamp the response was generated | 生成响应的时间戳
        time_zone:
          type: string
          title: Time Zone
          description: The timezone of the response time | 响应时间的时区
          default: America/Los_Angeles
        docs:
          anyOf:
            - type: string
            - type: 'null'
          title: Docs
          description: >-
            Link to the API Swagger documentation for this endpoint | 此端点的 API
            Swagger 文档链接
        cache_message:
          anyOf:
            - type: string
            - type: 'null'
          title: Cache Message
          description: Cache message (EN-US) | 缓存消息 (English)
          default: >-
            This request will be cached. You can access the cached result
            directly using the URL below, valid for 24 hours. Accessing the
            cache will not incur additional charges.
        cache_message_zh:
          anyOf:
            - type: string
            - type: 'null'
          title: Cache Message Zh
          description: Cache message (ZH-CN) | 缓存消息 (中文)
          default: 本次请求将被缓存，你可以使用下面的 URL 直接访问缓存结果，有效期为 24 小时，访问缓存不会产生额外费用。
        cache_url:
          anyOf:
            - type: string
            - type: 'null'
          title: Cache Url
          description: The URL to access the cached result | 访问缓存结果的 URL
        router:
          type: string
          title: Router
          description: The endpoint that generated this response | 生成此响应的端点
          default: ''
        params:
          type: string
        data:
          anyOf:
            - type: string
            - type: 'null'
          title: Data
          description: The response data | 响应数据
      type: object
      title: ResponseModel
      x-apifox-orders:
        - code
        - request_id
        - message
        - message_zh
        - support
        - time
        - time_stamp
        - time_zone
        - docs
        - cache_message
        - cache_message_zh
        - cache_url
        - router
        - params
        - data
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    HTTPValidationError:
      properties:
        detail:
          items:
            $ref: '#/components/schemas/ValidationError'
          type: array
          title: Detail
      type: object
      title: HTTPValidationError
      x-apifox-orders:
        - detail
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
    ValidationError:
      properties:
        loc:
          items:
            anyOf:
              - type: string
              - type: integer
          type: array
          title: Location
        msg:
          type: string
          title: Message
        type:
          type: string
          title: Error Type
      type: object
      required:
        - loc
        - msg
        - type
      title: ValidationError
      x-apifox-orders:
        - loc
        - msg
        - type
      x-apifox-ignore-properties: []
      x-apifox-folder: ''
  securitySchemes:
    Bearer Token:
      type: bearer
      scheme: bearer
    HTTPBearer:
      type: bearer
      description: >
        ----

        #### API Token Introduction:

        ##### Method 1: Use API Token in the Request Header (Recommended)

        - **Header**: `Authorization`

        - **Format**: `Bearer {token}`

        - **Example**: `{"Authorization": "Bearer your_token"}`

        - **Swagger UI**: Click on the `Authorize` button in the upper right
        corner of the page to enter the API token directly without the `Bearer`
        keyword.


        ##### Method 2: Use API Token in the Cookie (Not Recommended, Use Only
        When Method 1 is Unavailable)

        - **Cookie**: `Authorization`

        - **Format**: `Bearer {token}`

        - **Example**: `Authorization=Bearer your_token`


        #### Get API Token:

        1. Register and log in to your account on the TikHub website.

        2. Go to the user center, click on the API token menu, and create an API
        token.

        3. Copy and use the API token in the request header.

        4. Keep your API token confidential and use it only in the request
        header.


        ----


        #### API令牌简介:

        ##### 方法一：在请求头中使用API令牌（推荐）

        - **请求头**: `Authorization`

        - **格式**: `Bearer {token}`

        - **示例**: `{"Authorization": "Bearer your_token"}`

        - **Swagger UI**: 点击页面右上角的`Authorize`按钮，直接输入API令牌，不需要`Bearer`关键字。


        ##### 方法二：在Cookie中使用API令牌（不推荐，仅在无法使用方法一时使用）

        - **Cookie**: `Authorization`

        - **格式**: `Bearer {token}`

        - **示例**: `Authorization=Bearer your_token`


        #### 获取API令牌:

        1. 在TikHub网站注册并登录账户。

        2. 进入用户中心，点击API令牌菜单，创建API令牌。

        3. 复制并在请求头中使用API令牌。

        4. 保密您的API令牌，仅在请求头中使用。
      scheme: bearer
servers:
  - url: https://api.tikhub.io
    description: Production Environment
security: []

```