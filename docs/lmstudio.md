# Docs for LMStudio SDK

## Basic

Use `llm.respond(...)` to generate completions for a chat conversation.

Quick Example: Generate a Chat Response [#quick-example-generate-a-chat-response]

The following snippet shows how to obtain the AI's response to a quick chat prompt.

<CodeBlockTabs defaultValue="Python (convenience API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Python (convenience API)">
      Python (convenience API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (scoped resource API)">
      Python (scoped resource API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (asynchronous API)">
      Python (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Python (convenience API)">
    ```python
    import lmstudio as lms

    model = lms.llm()
    print(model.respond("What is the meaning of life?"))
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (scoped resource API)">
    ```python
    import lmstudio as lms

    with lms.Client() as client:
        model = client.llm.model()
        print(model.respond("What is the meaning of life?"))
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    import lmstudio as lms

    async with lms.AsyncClient() as client:
        model = await client.llm.model()
        print(await model.respond("What is the meaning of life?"))
    ```

  </CodeBlockTab>
</CodeBlockTabs>

Streaming a Chat Response [#streaming-a-chat-response]

The following snippet shows how to stream the AI's response to a chat prompt,
displaying text fragments as they are received (rather than waiting for the
entire response to be generated before displaying anything).

<CodeBlockTabs defaultValue="Python (convenience API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Python (convenience API)">
      Python (convenience API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (scoped resource API)">
      Python (scoped resource API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (asynchronous API)">
      Python (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Python (convenience API)">
    ```python
    import lmstudio as lms
    model = lms.llm()

    for fragment in model.respond_stream("What is the meaning of life?"):
        print(fragment.content, end="", flush=True)
    print() # Advance to a new line at the end of the response
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (scoped resource API)">
    ```python
    import lmstudio as lms

    with lms.Client() as client:
        model = client.llm.model()

        for fragment in model.respond_stream("What is the meaning of life?"):
            print(fragment.content, end="", flush=True)
        print() # Advance to a new line at the end of the response
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    import lmstudio as lms

    async with lms.AsyncClient() as client:
        model = await client.llm.model()

        async for fragment in model.respond_stream("What is the meaning of life?"):
            print(fragment.content, end="", flush=True)
        print() # Advance to a new line at the end of the response
    ```

  </CodeBlockTab>
</CodeBlockTabs>

Cancelling a Chat Response [#cancelling-a-chat-response]

See the [Cancelling a Prediction](./cancelling-predictions) section for how to cancel a prediction in progress.

Obtain a Model [#obtain-a-model]

First, you need to get a model handle.
This can be done using the top-level `llm` convenience API,
or the `model` method in the `llm` namespace when using the scoped resource API.
For example, here is how to use Qwen2.5 7B Instruct.

<CodeBlockTabs defaultValue="Python (convenience API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Python (convenience API)">
      Python (convenience API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (scoped resource API)">
      Python (scoped resource API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (asynchronous API)">
      Python (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Python (convenience API)">
    ```python
    import lmstudio as lms

    model = lms.llm("qwen2.5-7b-instruct")
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (scoped resource API)">
    ```python
    import lmstudio as lms

    with lms.Client() as client:
        model = client.llm.model("qwen2.5-7b-instruct")
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    import lmstudio as lms

    async with lms.AsyncClient() as client:
        model = await client.llm.model("qwen2.5-7b-instruct")
    ```

  </CodeBlockTab>
</CodeBlockTabs>

There are other ways to get a model handle. See [Managing Models in Memory](./../manage-models/loading) for more info.

Manage Chat Context [#manage-chat-context]

The input to the model is referred to as the "context".
Conceptually, the model receives a multi-turn conversation as input,
and it is asked to predict the assistant's response in that conversation.

```python
import lmstudio as lms

# Create a chat with an initial system prompt.
chat = lms.Chat("You are a resident AI philosopher.")

# Build the chat context by adding messages of relevant types.
chat.add_user_message("What is the meaning of life?")
# ... continued in next example
```

See [Working with Chats](./working-with-chats) for more information on managing chat context.

<!-- , and [`Chat`](./../api-reference/chat) for API reference for the `Chat` class. -->

Generate a response [#generate-a-response]

You can ask the LLM to predict the next response in the chat context using the `respond()` method.

<CodeBlockTabs defaultValue="Non-streaming (synchronous API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Non-streaming (synchronous API)">
      Non-streaming (synchronous API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming (synchronous API)">
      Streaming (synchronous API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Non-streaming (asynchronous API)">
      Non-streaming (asynchronous API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming (asynchronous API)">
      Streaming (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Non-streaming (synchronous API)">
    ```python
    # The `chat` object is created in the previous step.
    result = model.respond(chat)

    print(result)
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Streaming (synchronous API)">
    ```python
    # The `chat` object is created in the previous step.
    prediction_stream = model.respond_stream(chat)

    for fragment in prediction_stream:
        print(fragment.content, end="", flush=True)
    print() # Advance to a new line at the end of the response
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Non-streaming (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    # The `chat` object is created in the previous step.
    result = await model.respond(chat)

    print(result)
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Streaming (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    # The `chat` object is created in the previous step.
    prediction_stream = await model.respond_stream(chat)

    async for fragment in prediction_stream:
        print(fragment.content, end="", flush=True)
    print() # Advance to a new line at the end of the response
    ```

  </CodeBlockTab>
</CodeBlockTabs>

Customize Inferencing Parameters [#customize-inferencing-parameters]

You can pass in inferencing parameters via the `config` keyword parameter on `.respond()`.

<CodeBlockTabs defaultValue="Non-streaming (synchronous API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Non-streaming (synchronous API)">
      Non-streaming (synchronous API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming (synchronous API)">
      Streaming (synchronous API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Non-streaming (asynchronous API)">
      Non-streaming (asynchronous API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming (asynchronous API)">
      Streaming (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Non-streaming (synchronous API)">
    ```python
    result = model.respond(chat, config={
        "temperature": 0.6,
        "maxTokens": 50,
    })
    ```
  </CodeBlockTab>

  <CodeBlockTab value="Streaming (synchronous API)">
    ```python
    prediction_stream = model.respond_stream(chat, config={
        "temperature": 0.6,
        "maxTokens": 50,
    })
    ```
  </CodeBlockTab>

  <CodeBlockTab value="Non-streaming (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    result = await model.respond(chat, config={
        "temperature": 0.6,
        "maxTokens": 50,
    })
    ```
  </CodeBlockTab>

  <CodeBlockTab value="Streaming (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    prediction_stream = await model.respond_stream(chat, config={
        "temperature": 0.6,
        "maxTokens": 50,
    })
    ```
  </CodeBlockTab>
</CodeBlockTabs>

See [Configuring the Model](./parameters) for more information on what can be configured.

Print prediction stats [#print-prediction-stats]

You can also print prediction metadata, such as the model used for generation, number of generated
tokens, time to first token, and stop reason.

<CodeBlockTabs defaultValue="Non-streaming">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Non-streaming">
      Non-streaming
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming">
      Streaming
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Non-streaming">
    ```python
    # `result` is the response from the model.
    print("Model used:", result.model_info.display_name)
    print("Predicted tokens:", result.stats.predicted_tokens_count)
    print("Time to first token (seconds):", result.stats.time_to_first_token_sec)
    print("Stop reason:", result.stats.stop_reason)
    ```
  </CodeBlockTab>

  <CodeBlockTab value="Streaming">
    ```python
    # After iterating through the prediction fragments,
    # the overall prediction result may be obtained from the stream
    result = prediction_stream.result()

    print("Model used:", result.model_info.display_name)
    print("Predicted tokens:", result.stats.predicted_tokens_count)
    print("Time to first token (seconds):", result.stats.time_to_first_token_sec)
    print("Stop reason:", result.stats.stop_reason)
    ```

  </CodeBlockTab>
</CodeBlockTabs>

Both the non-streaming and streaming result access is consistent across the synchronous and
asynchronous APIs, as `prediction_stream.result()` is a non-blocking API that raises an exception
if no result is available (either because the prediction is still running, or because the
prediction request failed). Prediction streams also offer a blocking (synchronous API) or
awaitable (asynchronous API) `prediction_stream.wait_for_result()` method that internally handles
iterating the stream to completion before returning the result.

Example: Multi-turn Chat [#example-multi-turn-chat]

```python title="chatbot.py"
import lmstudio as lms

model = lms.llm()
chat = lms.Chat("You are a task focused AI assistant")

while True:
    try:
        user_input = input("You (leave blank to exit): ")
    except EOFError:
        print()
        break
    if not user_input:
        break
    chat.add_user_message(user_input)
    prediction_stream = model.respond_stream(
        chat,
        on_message=chat.append,
    )
    print("Bot: ", end="", flush=True)
    for fragment in prediction_stream:
        print(fragment.content, end="", flush=True)
    print()
```

Progress Callbacks [#progress-callbacks]

Long prompts will often take a long time to first token, i.e. it takes the model a long time to process your prompt.
If you want to get updates on the progress of this process, you can provide a float callback to `respond`
that receives a float from 0.0-1.0 representing prompt processing progress.

<CodeBlockTabs defaultValue="Python (convenience API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Python (convenience API)">
      Python (convenience API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (scoped resource API)">
      Python (scoped resource API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (asynchronous API)">
      Python (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Python (convenience API)">
    ```python
    import lmstudio as lms

    llm = lms.llm()

    response = llm.respond(
        "What is LM Studio?",
        on_prompt_processing_progress = (lambda progress: print(f"{progress*100}% complete")),
    )
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (scoped resource API)">
    ```python
    import lmstudio as lms

    with lms.Client() as client:
        llm = client.llm.model()

        response = llm.respond(
            "What is LM Studio?",
            on_prompt_processing_progress = (lambda progress: print(f"{progress*100}% complete")),
        )
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    import lmstudio as lms

    async with lms.AsyncClient() as client:
        llm = await client.llm.model()

        response = await llm.respond(
            "What is LM Studio?",
            on_prompt_processing_progress = (lambda progress: print(f"{progress*100}% complete")),
        )
    ```

  </CodeBlockTab>
</CodeBlockTabs>

In addition to `on_prompt_processing_progress`, the other available progress callbacks are:

- `on_first_token`: called after prompt processing is complete and the first token is being emitted.
  Does not receive any arguments (use the streaming iteration API or `on_prediction_fragment`
  to process tokens as they are emitted).
- `on_prediction_fragment`: called for each prediction fragment received by the client.
  Receives the same prediction fragments as iterating over the stream iteration API.
- `on_message`: called with an assistant response message when the prediction is complete.
  Intended for appending received messages to a chat history instance.

## Config the Models

You can customize both inference-time and load-time parameters for your model. Inference parameters can be set on a per-request basis, while load parameters are set when loading the model.

Inference Parameters [#inference-parameters]

Set inference-time parameters such as `temperature`, `maxTokens`, `topP` and more.

<CodeBlockTabs defaultValue=".respond()">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value=".respond()">
      .respond()
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value=".complete()">
      .complete()
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value=".respond()">
    ```python
    result = model.respond(chat, config={
        "temperature": 0.6,
        "maxTokens": 50,
    })
    ```
  </CodeBlockTab>

  <CodeBlockTab value=".complete()">
    ```python
    result = model.complete(chat, config={
        "temperature": 0.6,
        "maxTokens": 50,
        "stopStrings": ["\n\n"],
      })
    ```
  </CodeBlockTab>
</CodeBlockTabs>

See [`LLMPredictionConfigInput`](./../../typescript/api-reference/llm-prediction-config-input) in the
Typescript SDK documentation for all configurable fields.

Note that while `structured` can be set to a JSON schema definition as an inference-time configuration parameter
(Zod schemas are not supported in the Python SDK), the preferred approach is to instead set the
[dedicated `response_format` parameter](<(./structured-responses)>), which allows you to more rigorously
enforce the structure of the output using a JSON or class based schema definition.

Load Parameters [#load-parameters]

Set load-time parameters such as the context length, GPU offload ratio, and more.

Set Load Parameters with `.model()` [#set-load-parameters-with-model]

The `.model()` retrieves a handle to a model that has already been loaded, or loads a new one on demand (JIT loading).

**Note**: if the model is already loaded, the given configuration will be **ignored**.

<CodeBlockTabs defaultValue="Python (convenience API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Python (convenience API)">
      Python (convenience API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (scoped resource API)">
      Python (scoped resource API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (asynchronous API)">
      Python (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Python (convenience API)">
    ```python
    import lmstudio as lms

    model = lms.llm("qwen2.5-7b-instruct", config={
        "contextLength": 8192,
        "gpu": {
          "ratio": 0.5,
        }
    })
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (scoped resource API)">
    ```python
    import lmstudio as lms

    with lms.Client() as client:
        model = client.llm.model(
            "qwen2.5-7b-instruct",
            config={
                "contextLength": 8192,
                "gpu": {
                  "ratio": 0.5,
                }
            }
        )
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    import lmstudio as lms

    async with lms.AsyncClient() as client:
        model = await client.llm.model(
            "qwen2.5-7b-instruct",
            config={
                "contextLength": 8192,
                "gpu": {
                  "ratio": 0.5,
                }
            }
        )
    ```

  </CodeBlockTab>
</CodeBlockTabs>

See [`LLMLoadModelConfig`](./../../typescript/api-reference/llm-load-model-config) in the
Typescript SDK documentation for all configurable fields.

Set Load Parameters with `.load_new_instance()` [#set-load-parameters-with-load_new_instance]

The `.load_new_instance()` method creates a new model instance and loads it with the specified configuration.

<CodeBlockTabs defaultValue="Python (convenience API)">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Python (convenience API)">
      Python (convenience API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (scoped resource API)">
      Python (scoped resource API)
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Python (asynchronous API)">
      Python (asynchronous API)
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Python (convenience API)">
    ```python
    import lmstudio as lms

    client = lms.get_default_client()
    model = client.llm.load_new_instance("qwen2.5-7b-instruct", config={
        "contextLength": 8192,
        "gpu": {
          "ratio": 0.5,
        }
    })
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (scoped resource API)">
    ```python
    import lmstudio as lms

    with lms.Client() as client:
        model = client.llm.load_new_instance(
            "qwen2.5-7b-instruct",
            config={
                "contextLength": 8192,
                "gpu": {
                  "ratio": 0.5,
                }
            }
        )
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Python (asynchronous API)">
    ```python
    # Note: assumes use of an async function or the "python -m asyncio" asynchronous REPL
    # Requires Python SDK version 1.5.0 or later
    import lmstudio as lms

    async with lms.AsyncClient() as client:
        model = await client.llm.load_new_instance(
            "qwen2.5-7b-instruct",
            config={
                "contextLength": 8192,
                "gpu": {
                  "ratio": 0.5,
                }
            }
        )
    ```

  </CodeBlockTab>
</CodeBlockTabs>

See [`LLMLoadModelConfig`](./../../typescript/api-reference/llm-load-model-config) in the
Typescript SDK documentation for all configurable fields.

## Structure Response

You can enforce a particular response format from an LLM by providing a JSON schema to the `.respond()` method.
This guarantees that the model's output conforms to the schema you provide.

The JSON schema can either be provided directly,
or by providing an object that implements the `lmstudio.ModelSchema` protocol,
such as `pydantic.BaseModel` or `lmstudio.BaseModel`.

The `lmstudio.ModelSchema` protocol is defined as follows:

```python
@runtime_checkable
class ModelSchema(Protocol):
    """Protocol for classes that provide a JSON schema for their model."""

    @classmethod
    def model_json_schema(cls) -> DictSchema:
        """Return a JSON schema dict describing this model."""
        ...

```

When a schema is provided, the prediction result's `parsed` field will contain a string-keyed dictionary that conforms
to the given schema (for unstructured results, this field is a string field containing the same value as `content`).

Enforce Using a Class Based Schema Definition [#enforce-using-a-class-based-schema-definition]

If you wish the model to generate JSON that satisfies a given schema,
it is recommended to provide a class based schema definition using a library
such as [`pydantic`](https://docs.pydantic.dev/) or [`msgspec`](https://jcristharif.com/msgspec/).

Pydantic models natively implement the `lmstudio.ModelSchema` protocol,
while `lmstudio.BaseModel` is a `msgspec.Struct` subclass that implements `.model_json_schema()` appropriately.

Define a Class Based Schema [#define-a-class-based-schema]

<CodeBlockTabs defaultValue="pydantic.BaseModel">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="pydantic.BaseModel">
      pydantic.BaseModel
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="lmstudio.BaseModel">
      lmstudio.BaseModel
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="pydantic.BaseModel">
    ```python
    from pydantic import BaseModel

    # A class based schema for a book
    class BookSchema(BaseModel):
        title: str
        author: str
        year: int
    ```

  </CodeBlockTab>

  <CodeBlockTab value="lmstudio.BaseModel">
    ```python
    from lmstudio import BaseModel

    # A class based schema for a book
    class BookSchema(BaseModel):
        title: str
        author: str
        year: int
    ```

  </CodeBlockTab>
</CodeBlockTabs>

Generate a Structured Response [#generate-a-structured-response]

<CodeBlockTabs defaultValue="Non-streaming">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Non-streaming">
      Non-streaming
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming">
      Streaming
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Non-streaming">
    ```python
    result = model.respond("Tell me about The Hobbit", response_format=BookSchema)
    book = result.parsed

    print(book)
    #           ^
    # Note that `book` is correctly typed as { title: string, author: string, year: number }
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Streaming">
    ```python
    prediction_stream = model.respond_stream("Tell me about The Hobbit", response_format=BookSchema)

    # Optionally stream the response
    # for fragment in prediction:
    #   print(fragment.content, end="", flush=True)
    # print()
    # Note that even for structured responses, the *fragment* contents are still only text

    # Get the final structured result
    result = prediction_stream.result()
    book = result.parsed

    print(book)
    #           ^
    # Note that `book` is correctly typed as { title: string, author: string, year: number }
    ```

  </CodeBlockTab>
</CodeBlockTabs>

Enforce Using a JSON Schema [#enforce-using-a-json-schema]

You can also enforce a structured response using a JSON schema.

Define a JSON Schema [#define-a-json-schema]

```python
# A JSON schema for a book
schema = {
  "type": "object",
  "properties": {
    "title": { "type": "string" },
    "author": { "type": "string" },
    "year": { "type": "integer" },
  },
  "required": ["title", "author", "year"],
}
```

Generate a Structured Response [#generate-a-structured-response-1]

<CodeBlockTabs defaultValue="Non-streaming">
  <CodeBlockTabsList>
    <CodeBlockTabsTrigger value="Non-streaming">
      Non-streaming
    </CodeBlockTabsTrigger>

    <CodeBlockTabsTrigger value="Streaming">
      Streaming
    </CodeBlockTabsTrigger>

  </CodeBlockTabsList>

  <CodeBlockTab value="Non-streaming">
    ```python
    result = model.respond("Tell me about The Hobbit", response_format=schema)
    book = result.parsed

    print(book)
    #     ^
    # Note that `book` is correctly typed as { title: string, author: string, year: number }
    ```

  </CodeBlockTab>

  <CodeBlockTab value="Streaming">
    ```python
    prediction_stream = model.respond_stream("Tell me about The Hobbit", response_format=schema)

    # Stream the response
    for fragment in prediction:
        print(fragment.content, end="", flush=True)
    print()
    # Note that even for structured responses, the *fragment* contents are still only text

    # Get the final structured result
    result = prediction_stream.result()
    book = result.parsed

    print(book)
    #     ^
    # Note that `book` is correctly typed as { title: string, author: string, year: number }
    ```

  </CodeBlockTab>
</CodeBlockTabs>

<!--

TODO: Info about structured generation caveats

 ## Overview

Once you have [downloaded and loaded](/docs/basics/index) a large language model,
you can use it to respond to input through the API. This article covers getting JSON structured output, but you can also
[request text completions](/docs/api/sdk/completion),
[request chat responses](/docs/api/sdk/chat-completion), and
[use a vision-language model to chat about images](/docs/api/sdk/image-input).

### Usage

Certain models are trained to output valid JSON data that conforms to
a user-provided schema, which can be used programmatically in applications
that need structured data. This structured data format is supported by both
[`complete`](/docs/api/sdk/completion) and [`respond`](/docs/api/sdk/chat-completion)
methods, and relies on Pydantic in Python and Zod in TypeScript.

```python
import { LMStudioClient } from "@lmstudio/sdk";
import { z } from "zod";

const Book = z.object({
  title: z.string(),
  author: z.string(),
  year: z.number().int()
})

const client = new LMStudioClient()
const llm = client.llm.model()

const response = llm.respond(
  "Tell me about The Hobbit.",
  { structured: Book },
)

console.log(response.content.title)
``` -->
