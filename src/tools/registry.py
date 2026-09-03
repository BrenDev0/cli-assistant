from src.tools.files.tools import (
    read_file,
    search_file,
    list_dir,
    create_file,
    create_dir,
    update_file,
    copy_path,
    move_path,
    delete_file,
    delete_dir
)
from src.tools.skills.tools import build_skill, list_skills
from src.tools.html.tools import build_html_page
from src.tools.ghl.tools import (
    search_ghl_operations,
    describe_operation,
    execute_ghl_operation,
)
from src.tools.background.tools import start_background_task, check_background_task, deliver_task
from src.tools.history.tools import search_conversation_history
from src.tools.web.tools import (
    web_search,
    map_web_pages,
    extract_web_pages,
    crawl_web_pages,
    web_research,
)
from .files.schemas import CreateDir, CreateFile, SearchFile, ListDir, ReadFile, UpdateFile, CopyPath, MovePath, DeleteFile, DeleteDir
from .skills.schemas import BuildSkill, ListSkills
from .html.schemas import BuildHtmlPage
from .ghl.schemas import (
    SearchGhlOperations,
    DescribeGhlOperation,
    ExecuteGhlOperation,
)
from .background.schemas import StartBackgroundTask, CheckBackgroundTask, DeliverTask
from .web.schemas import WebSearch, MapWebPages, ExtractWebPages, CrawlWebPages, WebResearch
from .history.schemas import SearchConversationHistory

TOOLS = {
    ReadFile: read_file,
    SearchFile: search_file,
    ListDir: list_dir,
    CreateFile: create_file,
    CreateDir: create_dir,
    UpdateFile: update_file,
    CopyPath: copy_path,
    MovePath: move_path,
    DeleteFile: delete_file,
    DeleteDir: delete_dir,
    BuildSkill: build_skill,
    ListSkills: list_skills,
    BuildHtmlPage: build_html_page,
    SearchGhlOperations: search_ghl_operations,
    DescribeGhlOperation: describe_operation,
    ExecuteGhlOperation: execute_ghl_operation,
    StartBackgroundTask: start_background_task,
    CheckBackgroundTask: check_background_task,
    DeliverTask: deliver_task,
    WebSearch: web_search,
    MapWebPages: map_web_pages,
    ExtractWebPages: extract_web_pages,
    CrawlWebPages: crawl_web_pages,
    # WebResearch: web_research,
    SearchConversationHistory: search_conversation_history
}

TOOL_REGISTRY = {cls.__name__: fn for cls, fn in TOOLS.items()}

SCHEMAS = list(TOOLS.keys())