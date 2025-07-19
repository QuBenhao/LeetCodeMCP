import logging
import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("leetcodemcp")

LANGUAGE = os.getenv("LANGUAGE", "zh-CN")

# Constants
LEET_CODE_API_BASE = "https://leetcode.cn/graphql/"
WANTED_AUTHORS = [("宫水三叶", "ac_oier"), ("灵茶山艾府", "endlesscheng")]

QUESTION_DESC_QUERY = """
query questionContent($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    content
    editorType
    mysqlSchemas
    dataSchemas
  }
}
"""

QUESTION_DESC_CN_QUERY = """
query questionTranslations($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    translatedTitle
    translatedContent
  }
}
"""

QUESTION_KEYWORDS_QUERY = """
query problemsetQuestionListV2($filters: QuestionFilterInput, $limit: Int, $searchKeyword: String, $skip: Int, $sortBy: QuestionSortByInput, $categorySlug: String) {
  problemsetQuestionListV2(
    filters: $filters
    limit: $limit
    searchKeyword: $searchKeyword
    skip: $skip
    sortBy: $sortBy
    categorySlug: $categorySlug
  ) {
    questions {
      id
      titleSlug
      title
      translatedTitle
      questionFrontendId
      paidOnly
      difficulty
      topicTags {
        name
        slug
        nameTranslated
      }
      status
      isInMyFavorites
      frequency
      acRate
      contestPoint
    }
    totalLength
    finishedLength
    hasMore
  }
}
"""

QUESTION_SOLUTION_ARTICLE_QUERY = """
    query questionTopicsList($questionSlug: String!, $skip: Int, $first: Int, $orderBy: SolutionArticleOrderBy, $userInput: String, $tagSlugs: [String!]) {
  questionSolutionArticles(
    questionSlug: $questionSlug
    skip: $skip
    first: $first
    orderBy: $orderBy
    userInput: $userInput
    tagSlugs: $tagSlugs
  ) {
    totalNum
    edges {
      node {
        rewardEnabled
        canEditReward
        uuid
        title
        slug
        sunk
        chargeType
        status
        identifier
        canEdit
        canSee
        reactionType
        hasVideo
        favoriteCount
        upvoteCount
        reactionsV2 {
          count
          reactionType
        }
        tags {
          name
          nameTranslated
          slug
          tagType
        }
        createdAt
        thumbnail
        author {
          username
          certificationLevel
          profile {
            userAvatar
            userSlug
            realName
            reputation
          }
        }
        summary
        topic {
          id
          commentCount
          viewCount
          pinned
        }
        byLeetcode
        isMyFavorite
        isMostPopular
        isEditorsPick
        hitCount
        videosInfo {
          videoId
          coverUrl
          duration
        }
      }
    }
  }
}
    """

QUESTION_SOLUTION_ARTICLE_CONTENT_QUERY = """
    query discussTopic($slug: String) {
  solutionArticle(slug: $slug, orderBy: DEFAULT) {
    ...solutionArticle
    content
    next {
      slug
      title
    }
    prev {
      slug
      title
    }
  }
}
    
    fragment solutionArticle on SolutionArticleNode {
  ipRegion
  rewardEnabled
  canEditReward
  uuid
  title
  content
  slateValue
  slug
  sunk
  chargeType
  status
  identifier
  canEdit
  canSee
  reactionType
  reactionsV2 {
    count
    reactionType
  }
  tags {
    name
    nameTranslated
    slug
    tagType
  }
  createdAt
  thumbnail
  author {
    username
    certificationLevel
    isDiscussAdmin
    isDiscussStaff
    profile {
      userAvatar
      userSlug
      realName
      reputation
    }
  }
  summary
  topic {
    id
    subscribed
    commentCount
    viewCount
    post {
      id
      status
      voteStatus
      isOwnPost
    }
  }
  byLeetcode
  isMyFavorite
  isMostPopular
  favoriteCount
  isEditorsPick
  hitCount
  videosInfo {
    videoId
    coverUrl
    duration
  }
  question {
    titleSlug
    questionFrontendId
  }
}
    """

def _folder_name_to_problem_id(folder_name: str) -> str:
    question_id = folder_name[folder_name.find("_") + 1:]
    if "__" in question_id:
        question_id = question_id.replace("__", ".")
    if "_" in question_id:
        question_id = question_id.replace("_", " ")
    if "JZ_Offer" in question_id:
        question_id = question_id.replace("JZ_Offer", "剑指Offer")
    if "Interview" in question_id:
        question_id = question_id.replace("Interview", "面试题")
    return question_id

async def _get_leetcode_question_desc_by_slug(slug: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            if LANGUAGE == "zh-CN":
                query_json = {"query": QUESTION_DESC_CN_QUERY,
                              "variables": {"titleSlug": slug},
                              "operationName": "questionTranslations"}
                resp_key = "translatedContent"
            else:
                query_json = {
                    "query": QUESTION_DESC_QUERY,
                    "variables": {"titleSlug": slug},
                    "operationName": "questionContent"}
                resp_key = "content"

            resp = await client.post(LEET_CODE_API_BASE,
                                     json=query_json,
                                     timeout=5.0)
            resp.raise_for_status()
            return resp.json()['data']['question'][resp_key]
        except Exception:
            return "No description found"

async def _get_leetcode_article(article_slug: str) -> str | None:
    async with httpx.AsyncClient() as client:
        try:
            query_json = {
                "query": QUESTION_SOLUTION_ARTICLE_CONTENT_QUERY,
                "variables": {"slug": article_slug},
                "operationName": "discussTopic"
            }
            resp = await client.post(LEET_CODE_API_BASE, json=query_json, timeout=5.0)
            resp.raise_for_status()
            article_data = resp.json()['data']['solutionArticle']
            if article_data and 'content' in article_data:
                return article_data['content']
        except Exception:
            logging.error(f"Error fetching article for slug: {article_slug}", exc_info=True)
    return None


@mcp.tool()
async def get_leetcode_question_solution_by_problem_id(problem_id: str) -> str:
    """
    Get problem solution and explanation by problem ID

    Args:
        problem_id (str): LeetCode problem ID
    """
    slug = await find_leetcode_question_slug_by_problem_id(problem_id)
    if slug == "No slug found":
        return "No solution article found"

    async with httpx.AsyncClient() as client:
        for author_name, author_slug in WANTED_AUTHORS:
            try:
                query_json = {
                    "query": QUESTION_SOLUTION_ARTICLE_QUERY,
                    "variables": {
                        "questionSlug": slug,
                        "skip": 0,
                        "first": 15,
                        "orderBy": "DEFAULT",
                        "userInput": author_name,
                        "tagSlugs": []
                    },
                    "operationName": "questionTopicsList"
                }
                resp = await client.post(LEET_CODE_API_BASE, json=query_json, timeout=5.0)
                resp.raise_for_status()
                articles = resp.json()['data']['questionSolutionArticles']["edges"]
                for article in articles:
                    profile = article["node"]["author"]["profile"]
                    if profile["realName"] == author_name or profile["userSlug"] == author_slug:
                        content = await _get_leetcode_article(article["node"]["slug"])
                        if content:
                            return content
            except Exception:
                logging.error(f"Error fetching solution article for {problem_id} by {author_name}", exc_info=True)
    return "Error fetching solution article"



@mcp.tool()
async def get_leetcode_question_solution(file_path: str) -> str:
    """
    Get problem solution and explanation by problem file

    Args:
        file_path (str): LeetCode problem file path
    """
    dir_path = Path(file_path).parent
    problem_id = _folder_name_to_problem_id(dir_path.name)
    return await get_leetcode_question_solution_by_problem_id(problem_id)


@mcp.tool()
async def get_leetcode_question_desc(file_path: str) -> str:
    """
    Find problem description (markdown content) from problem file

    Args:
        file_path (str): LeetCode problem file path
    """
    path = Path(file_path)
    dir_path = path.parent
    problem_file_name = "problem_zh.md" if LANGUAGE == "zh-CN" else "problem.md"
    problem_file_path = dir_path / problem_file_name
    if problem_file_path.exists():
        return problem_file_path.read_text()

    slug = await find_leetcode_question_slug(file_path)
    return await get_leetcode_question_desc(slug)

@mcp.tool()
async def get_leetcode_question_desc_by_problem_id(problem_id: str) -> str:
    """
    Get problem description by problem ID

    Args:
        problem_id (str): LeetCode problem ID
    """
    return await _get_leetcode_question_desc_by_slug(problem_id)


@mcp.tool()
async def find_leetcode_question_slug_by_problem_id(frontend_problem_id: str) -> str:
    """
    Find problem slug by LeetCode problem ID

    Args:
        frontend_problem_id (str): LeetCode problem ID (e.g., "1", "2", etc.)
    """
    try:
        page_size, page_no = 100, 0
        while True:
            filters = {
                "filterCombineType": "ALL",
                "statusFilter": {
                    "questionStatuses": [],
                    "operator": "IS"
                },
                "difficultyFilter": {
                    "difficulties": [],
                    "operator": "IS"
                },
                "languageFilter": {
                    "languageSlugs": [],
                    "operator": "IS"
                },
                "topicFilter": {
                    "topicSlugs": [],
                    "operator": "IS"
                },
                "acceptanceFilter": {},
                "frequencyFilter": {},
                "frontendIdFilter": {},
                "lastSubmittedFilter": {},
                "publishedFilter": {},
                "companyFilter": {
                    "companySlugs": [],
                    "operator": "IS"
                },
                "positionFilter": {
                    "positionSlugs": [],
                    "operator": "IS"
                },
                "contestPointFilter": {
                    "contestPoints": [],
                    "operator": "IS"
                },
                "premiumFilter": {
                    "premiumStatus": [],
                    "operator": "IS"
                }
            }
            async with httpx.AsyncClient() as client:
                result = await client.post("https://leetcode.cn/graphql",
                                           json={"query": QUESTION_KEYWORDS_QUERY,
                                                 "variables": {
                                                     "searchKeyword": frontend_problem_id,
                                                     "categorySlug": "all-code-essentials",
                                                     "skip": page_no * page_size, "limit": page_size,
                                                     "filters": filters
                                                 },
                                                 "operationName": "problemsetQuestionListV2"},
                                           timeout=5.0)
                result.raise_for_status()
                res_dict = result.json()["data"]["problemsetQuestionListV2"]
                for question in res_dict["questions"]:
                    if question["questionFrontendId"] == frontend_problem_id:
                        return question["titleSlug"]
                if not res_dict["hasMore"]:
                    break
            page_no += 1
    except Exception as _:
        logging.error(f"Error in getting questions by problem id: {frontend_problem_id}", exc_info=True)
    return "No slug found"

@mcp.tool()
async def find_leetcode_question_slug(file_path: str) -> str:
    """
    Find problem slug from problem file

    Args:
        file_path (str): LeetCode problem file path
    """
    path = Path(file_path)
    dir_path = path.parent
    keyword = _folder_name_to_problem_id(dir_path.name)
    return await find_leetcode_question_slug_by_problem_id(keyword)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
