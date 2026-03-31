using Microsoft.Extensions.Configuration;
using MicrosoftFoundry.Classic.Common;
using MicrosoftFoundry.Classic.Resources;

Console.WriteLine("Microsoft Foundry Agent Examples");
Console.WriteLine("================================");
Console.WriteLine();

try
{
    // Create configuration from user secrets and environment variables
    var configuration = FoundryClientFactory.CreateDefaultConfiguration();
    var factory = new FoundryClientFactory(configuration);

    // Load user secrets into environment variables for components that use Environment.GetEnvironmentVariable
    foreach (var kvp in configuration.AsEnumerable().Where(kvp => !string.IsNullOrEmpty(kvp.Value)))
    {
        Environment.SetEnvironmentVariable(kvp.Key, kvp.Value);
    }

    Console.WriteLine($"Project Endpoint: {factory.ProjectEndpoint}");
    Console.WriteLine($"Model Deployment: {factory.ModelDeploymentName}");
    Console.WriteLine();

    // Display menu options
    Console.WriteLine("Select an agent to run:");
    Console.WriteLine("  1. Basic Agent - Simple conversational agent");
    Console.WriteLine("  2. MCP Agent - Microsoft Learn documentation search");
    Console.WriteLine("  3. Custom MCP Agent - Custom MCP server integration");
    Console.WriteLine("  4. Custom MCP Agent (No Auth) - Custom MCP server without authentication");
    Console.WriteLine("  5. Content Filter Tester - Compare CF_Agent vs NF_Agent");
    Console.WriteLine("  6. Existing Agent - Retrieve and converse with a pre-existing agent");
    Console.WriteLine();
    Console.Write("Enter your choice (1-6): ");

    var choice = Console.ReadLine()?.Trim();

    Console.WriteLine();

    switch (choice)
    {
        case "1":
            var basicAgent = new BasicAgent(factory);
            await basicAgent.RunAsync();
            break;
        case "2":
            var mcpAgent = new MicrosoftLearnAgent(factory);
            await mcpAgent.RunAsync();
            break;
        case "3":
            var customMcpAgent = new CustomMCPAgent(factory);
            await customMcpAgent.RunAsync();
            break;
        case "4":
            var customMcpAgentNoAuth = new CustomMCPAgentNoAuth(factory);
            await customMcpAgentNoAuth.RunAsync();
            break;
        case "5":
            var filterTester = new ContentFilterTester(factory);
            await filterTester.RunAsync();
            break;
        case "6":
            Console.Write("Enter the existing agent ID: ");
            var agentId = Console.ReadLine()?.Trim();
            if (string.IsNullOrWhiteSpace(agentId))
            {
                Console.WriteLine("Agent ID is required.");
                break;
            }
            Console.Write("Enter additional instructions (or press Enter to skip): ");
            var additionalInstructions = Console.ReadLine()?.Trim();
            var existingAgent = new ExistingAgent(
                factory,
                agentId,
                string.IsNullOrWhiteSpace(additionalInstructions) ? null : additionalInstructions);
            await existingAgent.RunAsync();
            break;
        default:
            Console.WriteLine("Invalid choice. Please enter 1-6.");
            break;
    }
}
catch (InvalidOperationException ex)
{
    Console.WriteLine($"Configuration error: {ex.Message}");
    Console.WriteLine();
    Console.WriteLine("Please set the following in user secrets:");
    Console.WriteLine("  dotnet user-secrets set \"PROJECT_ENDPOINT\" \"<your-endpoint>\"");
    Console.WriteLine("  dotnet user-secrets set \"MODEL_DEPLOYMENT_NAME\" \"<your-model>\"");
}
catch (Exception ex)
{
    Console.WriteLine($"Error: {ex.Message}");
}
