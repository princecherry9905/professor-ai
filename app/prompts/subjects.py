"""Subjects the student can choose, with a short context line for the professor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    id: str
    name: str
    context: str


SUBJECTS: dict[str, Subject] = {
    s.id: s
    for s in [
        Subject("general", "General", "Any college-level computer science or study topic."),
        Subject("dsa", "Data Structures & Algorithms",
                "Data structures, algorithms, complexity analysis (Big-O), dry runs and "
                "university exam / coding-interview style problems."),
        Subject("os", "Operating Systems",
                "Processes, threads, CPU scheduling, synchronization, deadlocks, memory "
                "management, paging, file systems — as taught in undergraduate OS courses."),
        Subject("dbms", "DBMS",
                "Relational model, ER diagrams, SQL, normalization (1NF–BCNF), transactions, "
                "ACID, concurrency control, indexing — from a college-exam perspective."),
        Subject("cn", "Computer Networks",
                "OSI and TCP/IP models, protocols (HTTP, TCP, UDP, IP, DNS), routing, "
                "addressing, subnetting, congestion and flow control."),
        Subject("oop", "Object-Oriented Programming",
                "Classes, objects, encapsulation, inheritance, polymorphism, abstraction, "
                "SOLID principles and design patterns, with code examples."),
        Subject("javascript", "JavaScript",
                "Core JavaScript: types, scope, closures, prototypes, the event loop, "
                "promises/async-await, ES6+ features, DOM and Node.js basics."),
        Subject("python", "Python",
                "Python syntax, data types, functions, OOP in Python, modules, exceptions, "
                "comprehensions, generators and common standard-library tools."),
        Subject("ai", "Artificial Intelligence",
                "Search algorithms, knowledge representation, reasoning, agents, and an "
                "introduction to modern generative AI."),
        Subject("ml", "Machine Learning",
                "Supervised/unsupervised learning, regression, classification, evaluation "
                "metrics, overfitting, and introductory neural networks."),
        Subject("webdev", "Web Development",
                "HTML, CSS, frontend frameworks, REST APIs, backend basics, databases, "
                "authentication and deployment."),
        Subject("se", "Software Engineering",
                "SDLC models, requirements, UML, testing, version control, agile practices "
                "and software project management."),
    ]
}

DEFAULT_SUBJECT = "general"
