import scrapy
import os
import re


class ArxivSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = os.environ.get("CATEGORIES", "cs.CV")
        categories = categories.split(",")
        # 保存目标分类列表，用于后续验证
        self.target_categories = set(map(str.strip, categories))
        self.start_urls = [
            f"https://arxiv.org/list/{cat}/new" for cat in self.target_categories
        ]  # 起始URL（计算机科学领域的最新论文）

    name = "arxiv"  # 爬虫名称
    allowed_domains = ["arxiv.org"]  # 允许爬取的域名

    @staticmethod
    def _clean_text(selector):
        """将 arXiv 列表页节点中的换行与空白归一化为普通文本。"""
        # 列表页中的标题、摘要和注释会被多个 HTML 文本节点拆开，需要合并后再写入 JSONL。
        return " ".join(
            text.strip() for text in selector.xpath(".//text()").getall() if text.strip()
        )

    def parse(self, response):
        # 提取每篇论文的信息
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        # 遍历每篇论文的详细信息
        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue

            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            # 获取论文ID
            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue

            arxiv_id = abstract_link.split("/")[-1]

            # 获取对应的论文描述部分（dd 元素）
            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue

            # 提取论文分类信息，优先读取主分类。
            subjects_text = paper_dd.css(".list-subjects .primary-subject::text").get()
            if not subjects_text:
                subjects_text = self._clean_text(paper_dd.css(".list-subjects"))

            # 从分类文字中提取标准 arXiv 分类代码。
            categories_in_paper = re.findall(r"\(([^)]+)\)", subjects_text or "")
            paper_categories = set(categories_in_paper)
            if subjects_text and not paper_categories.intersection(self.target_categories):
                self.logger.debug(
                    f"Skipped paper {arxiv_id} with categories {paper_categories} "
                    f"(not in target {self.target_categories})"
                )
                continue

            # 标题位于列表页中，去除仅供页面展示使用的 "Title:" 前缀。
            title = re.sub(
                r"^Title:\s*", "", self._clean_text(paper_dd.css(".list-title"))
            )
            # 作者链接逐个对应论文作者，保留页面中的作者排序。
            authors = [
                self._clean_text(author) for author in paper_dd.css(".list-authors a")
            ]
            # Comments 字段并非每篇论文都有；缺失时使用空字符串保持旧 JSONL 接口稳定。
            comment = re.sub(
                r"^Comments:\s*", "", self._clean_text(paper_dd.css(".list-comments"))
            )
            # 列表页摘要已包含 arXiv 公开的原始摘要，无需再访问导出 API。
            summary = self._clean_text(paper_dd.css("p.mathjax"))
            # 使用页面中的分类顺序去重，避免集合转换造成输出顺序不稳定。
            ordered_categories = list(dict.fromkeys(categories_in_paper))

            yield {
                "id": arxiv_id,
                "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
                "abs": f"https://arxiv.org/abs/{arxiv_id}",
                "authors": authors,
                "title": title,
                "categories": ordered_categories,
                "comment": comment,
                "summary": summary,
            }
            self.logger.info(
                f"Found paper {arxiv_id} with categories {paper_categories}"
            )
