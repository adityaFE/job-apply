"""
Comprehensive skill taxonomy and extraction engine.
Handles synonyms, aliases, and robust regex word-boundary matching.
"""

import re
from typing import List, Set, Dict


# Skill mapping: Canonical Name -> List of aliases/patterns
SKILL_TAXONOMY: Dict[str, List[str]] = {
    # Languages
    "Python": [r"\bpython\b", r"\bpython3\b", r"\bpy\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\bes6\b", r"\becmascript\b"],
    "TypeScript": [r"\btypescript\b", r"\bts\b"],
    "Go": [r"\bgolang\b", r"\bgo\b(?!\s+(?:to|ahead|for|with|in|back|on|off|out|live))\b"],
    "Java": [r"\bjava\b(?!script)"],
    "C++": [r"\bc\+\+\b", r"\bcpp\b"],
    "C#": [r"\bc#\b", r"\bcsharp\b", r"\b\.net\b"],
    "Rust": [r"\brust\b", r"\brustlang\b"],
    "Ruby": [r"\bruby\b", r"\bruby on rails\b", r"\brails\b"],
    "PHP": [r"\bphp\b", r"\blaravel\b", r"\bsymfony\b"],
    "SQL": [r"\bsql\b", r"\brdbms\b"],
    "HTML": [r"\bhtml\b", r"\bhtml5\b"],
    "CSS": [r"\bcss\b", r"\bcss3\b", r"\bsass\b", r"\bscss\b"],
    "Scala": [r"\bscala\b"],
    "Kotlin": [r"\bkotlin\b"],
    "Swift": [r"\bswift\b"],

    # Web & Backend Frameworks
    "FastAPI": [r"\bfastapi\b", r"\bfast api\b"],
    "Django": [r"\bdjango\b", r"\bdjango rest\b", r"\bdrf\b"],
    "Flask": [r"\bflask\b"],
    "Node.js": [r"\bnode\.js\b", r"\bnodejs\b", r"\bnode\b"],
    "Express": [r"\bexpress\.js\b", r"\bexpressjs\b", r"\bexpress\b"],
    "NestJS": [r"\bnestjs\b", r"\bnest\.js\b"],
    "React": [r"\breact\b", r"\breact\.js\b", r"\breactjs\b"],
    "Next.js": [r"\bnext\.js\b", r"\bnextjs\b", r"\bnext\b"],
    "Vue": [r"\bvue\b", r"\bvue\.js\b", r"\bvuejs\b"],
    "Angular": [r"\bangular\b", r"\bangularjs\b"],
    "Tailwind": [r"\btailwind\b", r"\btailwindcss\b"],
    "Spring Boot": [r"\bspring boot\b", r"\bspring framework\b", r"\bspring\b"],
    "GraphQL": [r"\bgraphql\b", r"\bgql\b"],
    "REST API": [r"\brest\b", r"\brestful\b", r"\brest api\b", r"\bweb apis\b"],
    "gRPC": [r"\bgrpc\b", r"\bprotobuf\b", r"\bprotocol buffers\b"],

    # Databases & Caching
    "PostgreSQL": [r"\bpostgresql\b", r"\bpostgres\b", r"\bpsql\b"],
    "MySQL": [r"\bmysql\b"],
    "MongoDB": [r"\bmongodb\b", r"\bmongo\b"],
    "Redis": [r"\bredis\b"],
    "Elasticsearch": [r"\belasticsearch\b", r"\belastic\b", r"\belk\b"],
    "Cassandra": [r"\bcassandra\b"],
    "DynamoDB": [r"\bdynamodb\b", r"\bdynamo\b"],
    "Snowflake": [r"\bsnowflake\b"],
    "ClickHouse": [r"\bclickhouse\b"],
    "SQLite": [r"\bsqlite\b", r"\bsqlite3\b"],

    # Cloud & DevOps
    "AWS": [r"\baws\b", r"\bamazon web services\b", r"\bec2\b", r"\bs3\b", r"\blambda\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud\b", r"\bgoogle cloud platform\b"],
    "Azure": [r"\bazure\b", r"\bmicrosoft azure\b"],
    "Docker": [r"\bdocker\b", r"\bcontainerization\b", r"\bcontainers\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b", r"\bkube\b"],
    "Terraform": [r"\bterraform\b", r"\biac\b", r"\binfrastructure as code\b"],
    "CI/CD": [r"\bci/cd\b", r"\bcicd\b", r"\bgithub actions\b", r"\bgitlab ci\b", r"\bjenkins\b"],
    "Linux": [r"\blinux\b", r"\bunix\b", r"\bbash\b", r"\bshell\b"],
    "Git": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],

    # Messaging & Streaming
    "Kafka": [r"\bkafka\b", r"\bapache kafka\b"],
    "RabbitMQ": [r"\brabbitmq\b", r"\bamqp\b"],
    "Celery": [r"\bcelery\b"],

    # Architecture & Concepts
    "Microservices": [r"\bmicroservices\b", r"\bmicroservice architecture\b"],
    "System Design": [r"\bsystem design\b", r"\bhigh availability\b", r"\bscalability\b"],
    "TDD / Testing": [r"\btdd\b", r"\bunit tests\b", r"\bpytest\b", r"\bjest\b", r"\bcypress\b"],

    # Non-preferred / Omit Skills Taxonomy
    "WordPress": [r"\bwordpress\b", r"\bwp\b"],
    "Salesforce": [r"\bsalesforce\b", r"\bapex\b"],
    "COBOL": [r"\bcobol\b"],
    "Fortran": [r"\bfortran\b"],
    "Perl": [r"\bperl\b"],
    "Flash": [r"\bflash\b", r"\bactionscript\b"],
    "Manual QA": [r"\bmanual testing\b", r"\bmanual qa\b", r"\bqa tester\b"]
}


class SkillsExtractor:
    def __init__(self, custom_taxonomy: Dict[str, List[str]] = None):
        self.taxonomy = custom_taxonomy or SKILL_TAXONOMY
        self._compiled_regexes = {}
        self._compile_all()

    def _compile_all(self):
        for canonical, patterns in self.taxonomy.items():
            combined = "|".join(patterns)
            self._compiled_regexes[canonical] = re.compile(combined, re.IGNORECASE)

    def extract_skills(self, text: str) -> List[str]:
        """Extract all recognized canonical skills from arbitrary text."""
        if not text:
            return []

        found: Set[str] = set()
        for canonical, regex in self._compiled_regexes.items():
            if regex.search(text):
                found.add(canonical)

        return sorted(list(found))

    def has_skill(self, text: str, skill_name: str) -> bool:
        """Check if a specific skill is present in text."""
        if not text:
            return False

        regex = self._compiled_regexes.get(skill_name)
        if regex:
            return bool(regex.search(text))

        # Fallback exact word boundary match
        pattern = rf"\b{re.escape(skill_name)}\b"
        return bool(re.search(pattern, text, re.IGNORECASE))
