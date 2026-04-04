# 单条字符串 Embedding 测试
import numpy as np
from analysis_llm import ArkService

def main() -> None:
    text = "机器人行业景气度持续提升，龙头公司订单明显增长。"

    service = ArkService()
    vec = service.get_embedding(text)

    print("输入文本:", text)
    print("向量维度:", vec.shape[0])
    print("向量范数:", float(np.linalg.norm(vec)))
    print("前10个值:", vec[:10].tolist())

if __name__ == "__main__":
    main()