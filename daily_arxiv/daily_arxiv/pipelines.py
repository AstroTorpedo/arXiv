class DailyArxivPipeline:
    """保留 Scrapy 管道接口，但不再向 export.arxiv.org 发起二次请求。"""

    def process_item(self, item: dict, spider):
        # arXiv 列表页已提供后续 AI 总结所需字段，避免 GitHub Actions 被导出 API 拒绝。
        item.setdefault("pdf", f"https://arxiv.org/pdf/{item['id']}")
        item.setdefault("abs", f"https://arxiv.org/abs/{item['id']}")
        return item
