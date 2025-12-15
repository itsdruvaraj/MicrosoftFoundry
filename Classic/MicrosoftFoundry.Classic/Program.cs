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

    Console.WriteLine($"Project Endpoint: {factory.ProjectEndpoint}");
    Console.WriteLine($"Model Deployment: {factory.ModelDeploymentName}");
    Console.WriteLine();

    // Display menu options
    Console.WriteLine("Select an agent to run:");
    Console.WriteLine("  1. Basic Agent - Simple conversational agent");
    Console.WriteLine("  2. MCP Agent - Microsoft Learn documentation search");
    Console.WriteLine("  3. Custom MCP Agent - Custom MCP server integration");
    Console.WriteLine();
    Console.Write("Enter your choice (1, 2, or 3): ");

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
        default:
            Console.WriteLine("Invalid choice. Please enter 1, 2, or 3.");
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
