using Azure.AI.Agents.Persistent;
using Azure.Identity;
using Microsoft.Extensions.Configuration;

namespace MicrosoftFoundry.Classic.Common;

/// <summary>
/// Factory class providing common functionality for creating and managing Microsoft Foundry agent clients.
/// </summary>
public sealed class FoundryClientFactory
{
    /// <summary>
    /// Configuration key for the project endpoint.
    /// </summary>
    public const string ProjectEndpointKey = "PROJECT_ENDPOINT";

    /// <summary>
    /// Configuration key for the model deployment name.
    /// </summary>
    public const string ModelDeploymentNameKey = "MODEL_DEPLOYMENT_NAME";

    private readonly string _projectEndpoint;
    private readonly string _modelDeploymentName;
    private PersistentAgentsClient? _client;

    /// <summary>
    /// Gets the project endpoint for the Microsoft Foundry project.
    /// </summary>
    public string ProjectEndpoint => _projectEndpoint;

    /// <summary>
    /// Gets the model deployment name.
    /// </summary>
    public string ModelDeploymentName => _modelDeploymentName;

    /// <summary>
    /// Initializes a new instance of the <see cref="FoundryClientFactory"/> class using IConfiguration.
    /// </summary>
    /// <param name="configuration">The configuration to read settings from.</param>
    /// <exception cref="InvalidOperationException">Thrown when required configuration is missing.</exception>
    public FoundryClientFactory(IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(configuration);

        _projectEndpoint = configuration[ProjectEndpointKey]
            ?? throw new InvalidOperationException(
                $"Project endpoint is required. Set '{ProjectEndpointKey}' in user secrets or environment variables.");

        _modelDeploymentName = configuration[ModelDeploymentNameKey]
            ?? throw new InvalidOperationException(
                $"Model deployment name is required. Set '{ModelDeploymentNameKey}' in user secrets or environment variables.");
    }

    /// <summary>
    /// Initializes a new instance of the <see cref="FoundryClientFactory"/> class with explicit values.
    /// </summary>
    /// <param name="projectEndpoint">The Microsoft Foundry project endpoint.</param>
    /// <param name="modelDeploymentName">The model deployment name.</param>
    /// <exception cref="ArgumentException">Thrown when required parameters are null or empty.</exception>
    public FoundryClientFactory(string projectEndpoint, string modelDeploymentName)
    {
        if (string.IsNullOrWhiteSpace(projectEndpoint))
        {
            throw new ArgumentException("Project endpoint is required.", nameof(projectEndpoint));
        }

        if (string.IsNullOrWhiteSpace(modelDeploymentName))
        {
            throw new ArgumentException("Model deployment name is required.", nameof(modelDeploymentName));
        }

        _projectEndpoint = projectEndpoint;
        _modelDeploymentName = modelDeploymentName;
    }

    /// <summary>
    /// Creates the default configuration builder with user secrets and environment variables.
    /// </summary>
    /// <returns>A configured <see cref="IConfiguration"/>.</returns>
    public static IConfiguration CreateDefaultConfiguration()
    {
        return new ConfigurationBuilder()
            .AddUserSecrets<FoundryClientFactory>()
            .AddEnvironmentVariables()
            .Build();
    }

    /// <summary>
    /// Gets or creates a <see cref="PersistentAgentsClient"/> instance.
    /// </summary>
    /// <returns>A configured <see cref="PersistentAgentsClient"/>.</returns>
    public PersistentAgentsClient GetClient()
    {
        return _client ??= new PersistentAgentsClient(_projectEndpoint, new DefaultAzureCredential());
    }

    /// <summary>
    /// Creates a new agent with the specified configuration.
    /// </summary>
    /// <param name="name">The name of the agent.</param>
    /// <param name="instructions">The system instructions for the agent.</param>
    /// <param name="tools">Optional tools for the agent.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The created <see cref="PersistentAgent"/>.</returns>
    public async Task<PersistentAgent> CreateAgentAsync(
        string name,
        string instructions,
        IEnumerable<ToolDefinition>? tools = null,
        CancellationToken cancellationToken = default)
    {
        var client = GetClient();
        return await client.Administration.CreateAgentAsync(
            model: _modelDeploymentName,
            name: name,
            instructions: instructions,
            tools: tools,
            cancellationToken: cancellationToken);
    }

    /// <summary>
    /// Creates a new thread for agent communication.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The created <see cref="PersistentAgentThread"/>.</returns>
    public async Task<PersistentAgentThread> CreateThreadAsync(CancellationToken cancellationToken = default)
    {
        var client = GetClient();
        return await client.Threads.CreateThreadAsync(cancellationToken: cancellationToken);
    }

    /// <summary>
    /// Sends a message in a thread and waits for the agent to complete processing.
    /// </summary>
    /// <param name="thread">The thread to send the message in.</param>
    /// <param name="agent">The agent to run.</param>
    /// <param name="userMessage">The user message to send.</param>
    /// <param name="additionalInstructions">Optional additional instructions for this run.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The completed <see cref="ThreadRun"/>.</returns>
    public async Task<ThreadRun> SendMessageAndRunAsync(
        PersistentAgentThread thread,
        PersistentAgent agent,
        string userMessage,
        string? additionalInstructions = null,
        CancellationToken cancellationToken = default)
    {
        var client = GetClient();

        // Create the user message
        await client.Messages.CreateMessageAsync(
            thread.Id,
            MessageRole.User,
            userMessage,
            cancellationToken: cancellationToken);

        // Create and run the agent
        ThreadRun run = await client.Runs.CreateRunAsync(
            thread.Id,
            agent.Id,
            additionalInstructions: additionalInstructions,
            cancellationToken: cancellationToken);

        // Wait for completion
        return await WaitForRunCompletionAsync(thread.Id, run.Id, cancellationToken);
    }

    /// <summary>
    /// Waits for a run to complete.
    /// </summary>
    /// <param name="threadId">The thread ID.</param>
    /// <param name="runId">The run ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The completed <see cref="ThreadRun"/>.</returns>
    public async Task<ThreadRun> WaitForRunCompletionAsync(
        string threadId,
        string runId,
        CancellationToken cancellationToken = default)
    {
        var client = GetClient();
        ThreadRun run;

        do
        {
            await Task.Delay(TimeSpan.FromMilliseconds(500), cancellationToken);
            run = await client.Runs.GetRunAsync(threadId, runId, cancellationToken);
        }
        while (run.Status == RunStatus.Queued || run.Status == RunStatus.InProgress);

        return run;
    }

    /// <summary>
    /// Gets all messages from a thread.
    /// </summary>
    /// <param name="threadId">The thread ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>A list of messages in the thread.</returns>
    public async Task<List<PersistentThreadMessage>> GetMessagesAsync(
        string threadId,
        CancellationToken cancellationToken = default)
    {
        var client = GetClient();
        var messages = client.Messages.GetMessagesAsync(threadId, cancellationToken: cancellationToken);
        return await messages.ToListAsync(cancellationToken);
    }

    /// <summary>
    /// Cleans up an agent and thread.
    /// </summary>
    /// <param name="agent">The agent to delete.</param>
    /// <param name="thread">The thread to delete.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    public async Task CleanupAsync(
        PersistentAgent? agent,
        PersistentAgentThread? thread,
        CancellationToken cancellationToken = default)
    {
        var client = GetClient();

        if (thread is not null)
        {
            await client.Threads.DeleteThreadAsync(thread.Id, cancellationToken);
        }

        if (agent is not null)
        {
            await client.Administration.DeleteAgentAsync(agent.Id, cancellationToken);
        }
    }

    /// <summary>
    /// Displays the latest agent response from a thread.
    /// </summary>
    /// <param name="threadId">The thread ID.</param>
    /// <param name="prefix">Optional prefix to display before the response (e.g., "Assistant: ").</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The text of the latest agent response, or null if none found.</returns>
    public async Task<string?> DisplayLatestResponseAsync(
        string threadId,
        string prefix = "[Agent]: ",
        CancellationToken cancellationToken = default)
    {
        var client = GetClient();

        await foreach (var message in client.Messages.GetMessagesAsync(
            threadId: threadId,
            order: ListSortOrder.Descending,
            cancellationToken: cancellationToken))
        {
            if (message.Role == MessageRole.Agent)
            {
                foreach (var contentItem in message.ContentItems)
                {
                    if (contentItem is MessageTextContent textItem)
                    {
                        Console.WriteLine($"{prefix}{textItem.Text}");
                        return textItem.Text;
                    }
                }
                break;
            }
        }

        return null;
    }

    /// <summary>
    /// Extracts text content from agent messages.
    /// </summary>
    /// <param name="messages">The messages to extract text from.</param>
    /// <returns>Formatted text content from assistant messages.</returns>
    public static string ExtractAssistantResponses(IEnumerable<PersistentThreadMessage> messages)
    {
        var responses = new List<string>();

        foreach (var message in messages.Where(m => m.Role == MessageRole.Agent))
        {
            foreach (var content in message.ContentItems)
            {
                if (content is MessageTextContent textContent)
                {
                    responses.Add(textContent.Text);
                }
            }
        }

        return string.Join(Environment.NewLine, responses);
    }
}
